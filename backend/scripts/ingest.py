"""Apply a delta SQLite file to the dashboard's SQLite database.

This runs *inside* the production container (it is copied into the image) and
uses only the standard library. The delta files are produced on a campus
Windows PC by `sync_to_aws.py`, copied to the instance over SSH, and applied
with:

    python scripts/ingest.py state                    # JSON watermark per table
    python scripts/ingest.py import /incoming/x.db    # apply one delta file
    python scripts/ingest.py mark                     # log a sync that found nothing new
    python scripts/ingest.py init                     # WAL mode + indexes only

Every successful `import` or `mark` appends a row to `_sync_log`, which the API
exposes as /api/sync/status ("data last synced at ...").

A delta file holds the same-named tables as the main database (only the new
rows) plus a `_sync_meta` table describing, per table, the key column, the
watermark the rows were selected above, and the mode:

    append  - rows with key > watermark are replaced by the delta's rows
              (re-applying the same delta is therefore harmless)
    replace - the whole table is dropped and rebuilt from the delta
              (used for the initial full load)

The database path comes from --db, else DATABASE_URL (sqlite:///...), else
/app/data/parsivel.db.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = "/app/data/parsivel.db"
META_TABLE = "_sync_meta"
SYNC_LOG_TABLE = "_sync_log"

# Source tables and the monotonic column used as the sync watermark.
# cpuTimestamp is stored as TEXT 'YYYY-MM-DD HH:MM:SS.ffffff', which sorts
# correctly as a string. histogram_id is an increasing integer id.
KEY_COLUMNS: dict[str, str] = {
    "parsivel_OTT": "cpuTimestamp",
    "parsivel_avg_ps": "cpuTimestamp",
    "parsivel_avg_ved": "cpuTimestamp",
    "parsivel_ved_histogram": "histogram_id",
    "parsivel_ved_histogram_value": "histogram_id",
}

# Indexes kept on the main database so watermark lookups and deletes are cheap.
INDEXES: dict[str, tuple[str, str]] = {
    "ix_parsivel_OTT_cpuTimestamp": ("parsivel_OTT", "cpuTimestamp"),
    "ix_parsivel_avg_ps_cpuTimestamp": ("parsivel_avg_ps", "cpuTimestamp"),
    "ix_parsivel_avg_ved_cpuTimestamp": ("parsivel_avg_ved", "cpuTimestamp"),
    "ix_parsivel_ved_histogram_value_histogram_id": (
        "parsivel_ved_histogram_value",
        "histogram_id",
    ),
}


def resolve_db_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return Path(DEFAULT_DB)


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, table: str, schema: str = "main") -> bool:
    row = conn.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA {schema}.table_info({_q(table)})")]


def ensure_indexes(conn: sqlite3.Connection) -> None:
    for name, (table, col) in INDEXES.items():
        if table_exists(conn, table):
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {_q(name)} ON {_q(table)} ({_q(col)})"
            )


def ensure_sync_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_q(SYNC_LOG_TABLE)} ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, synced_at TEXT NOT NULL, "
        "rows_inserted INTEGER NOT NULL, source TEXT)"
    )


def record_sync(conn: sqlite3.Connection, rows_inserted: int, source: str | None) -> str:
    """Append a row to the sync log. Returns the UTC timestamp written."""
    ensure_sync_log(conn)
    synced_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        f"INSERT INTO {_q(SYNC_LOG_TABLE)} (synced_at, rows_inserted, source) VALUES (?, ?, ?)",
        (synced_at, rows_inserted, source),
    )
    return synced_at


def read_last_sync(conn: sqlite3.Connection) -> dict[str, object] | None:
    if not table_exists(conn, SYNC_LOG_TABLE):
        return None
    row = conn.execute(
        f"SELECT synced_at, rows_inserted, source FROM {_q(SYNC_LOG_TABLE)} ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {"synced_at": row[0], "rows_inserted": row[1], "source": row[2]}


def init_db(conn: sqlite3.Connection) -> None:
    """Idempotent setup: WAL so readers never block the twice-daily import."""
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_indexes(conn)
    ensure_sync_log(conn)
    conn.commit()


def read_state(conn: sqlite3.Connection) -> dict[str, object]:
    """Current watermark (max key) per known table; None if table is absent/empty."""
    state: dict[str, object] = {}
    for table, key in KEY_COLUMNS.items():
        if table_exists(conn, table):
            state[table] = conn.execute(
                f"SELECT MAX({_q(key)}) FROM {_q(table)}"
            ).fetchone()[0]
        else:
            state[table] = None
    return state


def write_meta(
    delta: sqlite3.Connection,
    table: str,
    key_column: str,
    watermark: object,
    mode: str,
    row_count: int,
) -> None:
    """Record how a delta table was exported (called by sync_to_aws.py)."""
    delta.execute(
        f"CREATE TABLE IF NOT EXISTS {_q(META_TABLE)} ("
        "table_name TEXT PRIMARY KEY, key_column TEXT NOT NULL, watermark, "
        "mode TEXT NOT NULL, row_count INTEGER NOT NULL, exported_at TEXT NOT NULL)"
    )
    delta.execute(
        f"INSERT OR REPLACE INTO {_q(META_TABLE)} VALUES (?, ?, ?, ?, ?, ?)",
        (
            table,
            key_column,
            watermark,
            mode,
            row_count,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    delta.commit()


def apply_delta(conn: sqlite3.Connection, delta_path: Path) -> dict[str, dict[str, object]]:
    """Apply one delta file inside a single transaction. Returns per-table stats."""
    if not delta_path.is_file():
        raise FileNotFoundError(delta_path)

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("ATTACH DATABASE ? AS delta", (str(delta_path),))
    if not table_exists(conn, META_TABLE, "delta"):
        conn.execute("DETACH DATABASE delta")
        raise ValueError(f"{delta_path} has no {META_TABLE} table; not a sync delta")

    meta = conn.execute(
        f"SELECT table_name, key_column, watermark, mode, row_count FROM delta.{_q(META_TABLE)}"
    ).fetchall()

    stats: dict[str, dict[str, object]] = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        for table, key, watermark, mode, expected in meta:
            if not table_exists(conn, table, "delta"):
                raise ValueError(f"delta lists {table} in {META_TABLE} but has no such table")
            create_sql = conn.execute(
                "SELECT sql FROM delta.sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]

            deleted = 0
            if mode == "replace":
                conn.execute(f"DROP TABLE IF EXISTS main.{_q(table)}")
                conn.execute(create_sql)
            elif mode == "append":
                if not table_exists(conn, table):
                    conn.execute(create_sql)
                elif watermark is not None:
                    deleted = conn.execute(
                        f"DELETE FROM main.{_q(table)} WHERE {_q(key)} > ?", (watermark,)
                    ).rowcount
            else:
                raise ValueError(f"{table}: unknown sync mode {mode!r}")

            cols = [c for c in table_columns(conn, table, "delta") if c in table_columns(conn, table)]
            col_list = ", ".join(_q(c) for c in cols)
            inserted = conn.execute(
                f"INSERT INTO main.{_q(table)} ({col_list}) SELECT {col_list} FROM delta.{_q(table)}"
            ).rowcount
            if inserted != expected:
                raise ValueError(f"{table}: delta claims {expected} rows, inserted {inserted}")
            stats[table] = {"mode": mode, "deleted": deleted, "inserted": inserted}

        ensure_indexes(conn)
        synced_at = record_sync(
            conn, sum(int(s["inserted"]) for s in stats.values()), delta_path.name
        )
        conn.execute("COMMIT")
        stats["_sync"] = {"synced_at": synced_at}
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("DETACH DATABASE delta")
    return stats


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120, isolation_level=None)
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", help="SQLite path (default: DATABASE_URL or /app/data/parsivel.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("state", help="print JSON watermark per table")
    sub.add_parser("init", help="enable WAL and create indexes")
    sub.add_parser("mark", help="log a successful sync that found no new rows")
    p_import = sub.add_parser("import", help="apply a delta file")
    p_import.add_argument("delta", help="path to the delta .db file")
    args = parser.parse_args(argv)

    db_path = resolve_db_path(args.db)
    conn = _connect(db_path)
    try:
        if args.command == "state":
            print(json.dumps(read_state(conn)))
        elif args.command == "init":
            init_db(conn)
            print(json.dumps({"db": str(db_path), "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0]}))
        elif args.command == "mark":
            synced_at = record_sync(conn, 0, None)
            print(json.dumps({"db": str(db_path), "synced_at": synced_at, "rows_inserted": 0}))
        elif args.command == "import":
            stats = apply_delta(conn, Path(args.delta))
            print(json.dumps({"db": str(db_path), "delta": args.delta, "tables": stats}))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
