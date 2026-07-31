"""One-time snapshot of the parsivel SQL Server database into a local SQLite file.

Run from a shell that can reach the database server with Windows integrated
auth (e.g. `runas /netonly /user:<domain>\\<user> cmd`, same as running the
backend):

    cd backend
    uv run python scripts/snapshot_to_sqlite.py --server <host> --database <db>

Output: backend/data/parsivel.db (overwritten if it exists), which the
production Docker image bakes in and serves read-only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import sqlite3
import sys
from pathlib import Path

import pyodbc

TABLES = [
    "parsivel_OTT",
    "parsivel_avg_ps",
    "parsivel_avg_ved",
    "parsivel_ved_histogram",
    "parsivel_ved_histogram_value",
]

BATCH_SIZE = 50_000
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "parsivel.db"


def _sqlite_type(python_type: type) -> str:
    if python_type in (int, bool):
        return "INTEGER"
    if python_type in (float, decimal.Decimal):
        return "REAL"
    if python_type in (bytes, bytearray, memoryview):
        return "BLOB"
    # str, datetime, date, time, uuid, ... all stored as TEXT
    return "TEXT"


def _adapt(value):
    """Convert a pyodbc value to what we store in SQLite."""
    if isinstance(value, dt.datetime):
        # Match SQLAlchemy's SQLite datetime format so strftime('%s', col)
        # in the series endpoint parses it.
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value


def copy_table(src: pyodbc.Connection, dest: sqlite3.Connection, table: str) -> int:
    cursor = src.cursor()
    cursor.execute(f"SELECT * FROM dbo.[{table}]")
    columns = [d[0] for d in cursor.description]
    col_defs = ", ".join(
        f'"{d[0]}" {_sqlite_type(d[1])}' for d in cursor.description
    )
    dest.execute(f'DROP TABLE IF EXISTS "{table}"')
    dest.execute(f'CREATE TABLE "{table}" ({col_defs})')

    placeholders = ", ".join("?" for _ in columns)
    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders})'

    total = 0
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        dest.executemany(insert_sql, [tuple(_adapt(v) for v in row) for row in rows])
        dest.commit()
        total += len(rows)
        print(f"  {table}: {total:,} rows...", end="\r", flush=True)
    cursor.close()
    print(f"  {table}: {total:,} rows    ")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True, help="SQL Server hostname")
    parser.add_argument("--database", required=True, help="Source database name")
    args = parser.parse_args()

    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={args.server};"
        f"Database={args.database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=yes;"
    )

    print(f"Connecting to source: {args.server}/{args.database} (trusted connection)")
    try:
        src = pyodbc.connect(conn_str, timeout=15)
    except pyodbc.Error as exc:
        print(f"ERROR: could not connect to SQL Server: {exc}", file=sys.stderr)
        print(
            "Hint: run from a `runas /netonly /user:<domain>\\<user> cmd` shell "
            "so Windows integrated auth works.",
            file=sys.stderr,
        )
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    dest = sqlite3.connect(OUT_PATH)
    dest.execute("PRAGMA journal_mode=OFF")
    dest.execute("PRAGMA synchronous=OFF")

    print(f"Writing snapshot to {OUT_PATH}")
    for table in TABLES:
        try:
            copy_table(src, dest, table)
        except pyodbc.Error as exc:
            print(f"  {table}: SKIPPED ({exc})", file=sys.stderr)

    print("Creating index on parsivel_OTT(cpuTimestamp)")
    dest.execute(
        'CREATE INDEX IF NOT EXISTS ix_parsivel_OTT_cpuTimestamp '
        'ON "parsivel_OTT" ("cpuTimestamp")'
    )
    dest.commit()
    dest.execute("VACUUM")
    dest.close()
    src.close()

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Done. {OUT_PATH} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
