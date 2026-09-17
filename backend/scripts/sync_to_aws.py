"""Push new parsivel rows from SQL Server to the AWS dashboard over SSH.

Runs on a campus Windows PC (Task Scheduler, twice a day). Each run:

  1. asks the container on the EC2 instance for its watermark per table
     (`ingest.py state`),
  2. pulls every source row above each watermark into a small delta SQLite
     file (using the read-only domain account via in-process impersonation),
  3. copies the file to the instance with scp and applies it with
     `ingest.py import`, then deletes it.

The job is stateless: if a run is missed, the next one catches up. Re-applying
a delta is harmless (see ingest.py).

Configuration is read from environment variables, optionally loaded from a
KEY=VALUE file (default: backend/.sync.env, gitignored):

    PARSIVEL_SQL_SERVER      SQL Server hostname
    PARSIVEL_SQL_DATABASE    source database name
    PARSIVEL_SQL_USER        DOMAIN\\account to read as (omit to use the
                             process's own Windows identity)
    PARSIVEL_SQL_PASSWORD    password for PARSIVEL_SQL_USER
    PARSIVEL_SSH_HOST        EC2 public IP or DNS name
    PARSIVEL_SSH_USER        default ec2-user
    PARSIVEL_SSH_KEY         path to the .pem key
    PARSIVEL_CONTAINER       default parsivel-demo
    PARSIVEL_REMOTE_INCOMING host directory bind-mounted at /incoming in the
                             container (default: incoming, relative to the SSH
                             user's home)
    PARSIVEL_TABLES          comma-separated subset (default: all five)

Usage:
    python scripts/sync_to_aws.py                 # incremental push
    python scripts/sync_to_aws.py --full          # full reload of every table
    python scripts/sync_to_aws.py --dry-run       # build the delta, don't ship it
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mssql_source  # noqa: E402
from ingest import KEY_COLUMNS, write_meta  # noqa: E402

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".sync.env"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing values."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass
class Config:
    sql_server: str
    sql_database: str
    sql_user: str | None
    sql_password: str | None
    ssh_host: str
    ssh_user: str
    ssh_key: Path
    container: str
    remote_incoming: str
    tables: list[str]

    @classmethod
    def from_env(cls) -> "Config":
        def req(name: str) -> str:
            value = os.environ.get(name, "").strip()
            if not value:
                raise SystemExit(f"missing required setting {name}")
            return value

        tables_raw = os.environ.get("PARSIVEL_TABLES", "").strip()
        tables = [t.strip() for t in tables_raw.split(",") if t.strip()] or list(KEY_COLUMNS)
        unknown = [t for t in tables if t not in KEY_COLUMNS]
        if unknown:
            raise SystemExit(f"unknown table(s) in PARSIVEL_TABLES: {unknown}")

        return cls(
            sql_server=req("PARSIVEL_SQL_SERVER"),
            sql_database=req("PARSIVEL_SQL_DATABASE"),
            sql_user=os.environ.get("PARSIVEL_SQL_USER") or None,
            sql_password=os.environ.get("PARSIVEL_SQL_PASSWORD") or None,
            ssh_host=req("PARSIVEL_SSH_HOST"),
            ssh_user=os.environ.get("PARSIVEL_SSH_USER", "ec2-user"),
            ssh_key=Path(req("PARSIVEL_SSH_KEY")),
            container=os.environ.get("PARSIVEL_CONTAINER", "parsivel-demo"),
            remote_incoming=os.environ.get("PARSIVEL_REMOTE_INCOMING", "incoming").rstrip("/"),
            tables=tables,
        )


# --- SSH -------------------------------------------------------------------

class Remote:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.target = f"{cfg.ssh_user}@{cfg.ssh_host}"
        self.common = [
            "-i", str(cfg.ssh_key),
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=20",
        ]

    def run(self, command: str) -> str:
        proc = subprocess.run(
            ["ssh", *self.common, self.target, command],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ssh failed ({proc.returncode}): {command}\n{proc.stderr.strip()}")
        return proc.stdout

    def upload(self, local: Path, remote_path: str) -> None:
        proc = subprocess.run(
            ["scp", *self.common, str(local), f"{self.target}:{remote_path}"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"scp failed ({proc.returncode}): {proc.stderr.strip()}")

    def ingest(self, args: str) -> str:
        return self.run(f"docker exec {self.cfg.container} python scripts/ingest.py {args}")


# --- Delta export ----------------------------------------------------------

def _source_watermark_param(key_column: str, watermark):
    """Convert a watermark from ingest.py state into a SQL Server parameter."""
    if watermark is None:
        return None
    if key_column == "cpuTimestamp":
        return dt.datetime.strptime(str(watermark), TIMESTAMP_FORMAT)
    return int(watermark)


def export_delta(
    src,
    delta_path: Path,
    tables: list[str],
    state: dict[str, object],
    full: bool,
    schema: str = "dbo",
) -> dict[str, int]:
    """Write rows above each table's watermark to `delta_path`. Returns row counts."""
    if delta_path.exists():
        delta_path.unlink()
    delta = sqlite3.connect(delta_path)
    delta.execute("PRAGMA journal_mode=OFF")
    delta.execute("PRAGMA synchronous=OFF")

    counts: dict[str, int] = {}
    try:
        for table in tables:
            key = KEY_COLUMNS[table]
            watermark = None if full else state.get(table)
            param = _source_watermark_param(key, watermark)
            sql = f"SELECT * FROM {schema}.[{table}]"
            params: tuple = ()
            if param is not None:
                sql += f" WHERE [{key}] > ?"
                params = (param,)
            sql += f" ORDER BY [{key}]"

            n = mssql_source.copy_query(src, delta, table, sql, params)
            mode = "replace" if full else "append"
            write_meta(delta, table, key, watermark, mode, n)
            counts[table] = n
            log(f"  {table}: {n:,} new rows (watermark {watermark!r})")
    finally:
        delta.commit()
        delta.close()
    return counts


# --- Main ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE,
                        help=f"KEY=VALUE settings file (default {DEFAULT_ENV_FILE})")
    parser.add_argument("--full", action="store_true",
                        help="reload every table from scratch instead of pushing deltas")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the delta file locally but do not upload or apply it")
    parser.add_argument("--keep", action="store_true",
                        help="keep the local delta file after the run")
    args = parser.parse_args(argv)

    load_env_file(args.env_file)
    cfg = Config.from_env()
    remote = Remote(cfg)

    log(f"sync start: {cfg.sql_server}/{cfg.sql_database} -> {cfg.ssh_host} ({cfg.container})")

    # 1. Watermarks from the instance.
    if args.full:
        state: dict[str, object] = {}
        log("full reload requested; ignoring remote watermarks")
    else:
        state = json.loads(remote.ingest("state"))
        log(f"remote state: {json.dumps(state)}")

    # 2. Delta from SQL Server.
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    work_dir = Path(tempfile.mkdtemp(prefix="parsivel-sync-"))
    delta_name = f"delta-{stamp}.db"
    delta_path = work_dir / delta_name
    try:
        with mssql_source.domain_credentials(cfg.sql_user, cfg.sql_password):
            who = cfg.sql_user or "current Windows identity"
            log(f"connecting to SQL Server as {who}")
            src = mssql_source.connect(cfg.sql_server, cfg.sql_database)
            try:
                counts = export_delta(src, delta_path, cfg.tables, state, args.full)
            finally:
                src.close()

        total = sum(counts.values())
        size_mb = delta_path.stat().st_size / (1024 * 1024)
        log(f"delta: {total:,} rows, {size_mb:.1f} MB -> {delta_path}")

        if args.dry_run:
            log("dry run; not uploading")
            return 0
        if total == 0 and not args.full:
            # Still stamp the instance so "data last synced" reflects this run.
            result = remote.ingest("mark")
            log(f"nothing new; marked sync on the instance: {result.strip()}")
            return 0

        # 3. Ship and apply.
        remote_file = f"{cfg.remote_incoming}/{delta_name}"
        log(f"uploading to {cfg.ssh_host}:{remote_file}")
        remote.upload(delta_path, remote_file)
        log("applying on the instance")
        result = remote.run(
            f"docker exec {cfg.container} python scripts/ingest.py import /incoming/{delta_name}"
            f" && rm -f {remote_file}"
        )
        log(f"applied: {result.strip()}")
        log("sync done")
        return 0
    finally:
        if args.keep or args.dry_run:
            log(f"delta kept at {delta_path}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # surface a one-line failure for the task log
        log(f"ERROR: {exc}")
        sys.exit(1)
