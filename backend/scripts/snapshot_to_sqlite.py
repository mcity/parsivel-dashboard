"""Full copy of the parsivel SQL Server database into a local SQLite file.

Useful for local development against real data, or to seed a fresh AWS volume
(see DEPLOY.md). For keeping the deployed copy current, use sync_to_aws.py.

Two ways to authenticate (both are Windows integrated auth; the read-only
account is a domain account, not a SQL login):

    # a) explicit domain account, works from any Windows PC
    set PARSIVEL_SQL_PASSWORD=...
    python scripts/snapshot_to_sqlite.py --server <host> --database <db> ^
        --user <DOMAIN>\\<account>

    # b) a shell that already has domain credentials (runas /netonly ...)
    python scripts/snapshot_to_sqlite.py --server <host> --database <db>

Output: backend/data/parsivel.db (overwritten if it exists), in WAL mode with
the same indexes the deployed database uses.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mssql_source  # noqa: E402
from ingest import KEY_COLUMNS, init_db  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "parsivel.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True, help="SQL Server hostname")
    parser.add_argument("--database", required=True, help="Source database name")
    parser.add_argument("--user", help="DOMAIN\\user to connect as (password from "
                                       "PARSIVEL_SQL_PASSWORD or --password)")
    parser.add_argument("--password", help="password for --user (prefer the env var)")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"output file (default {OUT_PATH})")
    args = parser.parse_args()

    password = args.password or os.environ.get("PARSIVEL_SQL_PASSWORD")
    who = args.user or "current Windows identity"
    print(f"Connecting to source: {args.server}/{args.database} as {who}")

    with mssql_source.domain_credentials(args.user, password):
        try:
            src = mssql_source.connect(args.server, args.database)
        except Exception as exc:  # pyodbc.Error or pywin32 error
            print(f"ERROR: could not connect to SQL Server: {exc}", file=sys.stderr)
            print(
                "Hint: pass --user DOMAIN\\name with PARSIVEL_SQL_PASSWORD set, or run "
                "from a `runas /netonly /user:DOMAIN\\name cmd` shell.",
                file=sys.stderr,
            )
            return 1

        out: Path = args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        for stale in (out, out.with_name(out.name + "-wal"), out.with_name(out.name + "-shm")):
            if stale.exists():
                stale.unlink()
        dest = sqlite3.connect(out)
        dest.execute("PRAGMA journal_mode=OFF")
        dest.execute("PRAGMA synchronous=OFF")

        print(f"Writing snapshot to {out}")
        for table in KEY_COLUMNS:
            try:
                n = mssql_source.copy_query(
                    src, dest, table, f"SELECT * FROM dbo.[{table}]",
                    progress=lambda m: print(m, end="\r", flush=True),
                )
                print(f"  {table}: {n:,} rows    ")
            except Exception as exc:
                print(f"  {table}: SKIPPED ({exc})", file=sys.stderr)
        src.close()

    print("Creating indexes and enabling WAL")
    init_db(dest)
    dest.execute("VACUUM")
    dest.close()

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"Done. {out} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
