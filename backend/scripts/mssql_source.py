"""Shared helpers for reading the parsivel SQL Server database into SQLite.

Used by `snapshot_to_sqlite.py` (full copy) and `sync_to_aws.py` (deltas).

Authentication is always Windows integrated auth, because the read-only
account is a Windows domain account, not a SQL login.
`domain_credentials()` lets a script log in as that account from any Windows
machine, domain-joined or not: it does in-process what `runas /netonly` does,
so the calling process's own account is irrelevant.
"""

from __future__ import annotations

import datetime as dt
import decimal
import sqlite3
import sys
from contextlib import contextmanager
from typing import Callable, Iterator

import pyodbc

BATCH_SIZE = 50_000


@contextmanager
def domain_credentials(user: str | None, password: str | None) -> Iterator[None]:
    """Impersonate `DOMAIN\\user` for outbound network auth (NEW_CREDENTIALS logon).

    With no user given this is a no-op and the process's own Windows identity
    is used (e.g. a scheduled task running as the service account on a
    domain-joined PC, or a shell started with `runas /netonly`).
    """
    if not user:
        yield
        return
    if sys.platform != "win32":
        raise RuntimeError("domain_credentials() requires Windows (pywin32)")
    if not password:
        raise ValueError("a password is required when a domain user is given")

    import win32con
    import win32security

    if "\\" in user:
        domain, name = user.split("\\", 1)
    elif "@" in user:
        name, domain = user.split("@", 1)
    else:
        raise ValueError("user must be DOMAIN\\name or name@domain")

    token = win32security.LogonUser(
        name,
        domain,
        password,
        win32con.LOGON32_LOGON_NEW_CREDENTIALS,
        win32con.LOGON32_PROVIDER_WINNT50,
    )
    win32security.ImpersonateLoggedOnUser(token)
    try:
        yield
    finally:
        win32security.RevertToSelf()
        token.Close()


def connect(server: str, database: str, timeout: int = 15) -> pyodbc.Connection:
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};"
        f"Database={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=yes;"
    )
    return pyodbc.connect(conn_str, timeout=timeout)


def sqlite_type(python_type: type | None) -> str:
    if python_type in (int, bool):
        return "INTEGER"
    if python_type in (float, decimal.Decimal):
        return "REAL"
    if python_type in (bytes, bytearray, memoryview):
        return "BLOB"
    # str, datetime, date, time, uuid, None (unknown) ... stored as TEXT
    return "TEXT"


def adapt(value):
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


def copy_query(
    src,
    dest: sqlite3.Connection,
    table: str,
    sql: str,
    params: tuple = (),
    progress: Callable[[str], None] | None = None,
) -> int:
    """Run `sql` on the source and (re)create `table` in `dest` with its rows.

    `src` is any DB-API connection whose cursor exposes `.description` with
    (name, type) pairs. Returns the number of rows copied.
    """
    cursor = src.cursor()
    cursor.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    col_defs = ", ".join(f'"{d[0]}" {sqlite_type(d[1])}' for d in cursor.description)
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
        dest.executemany(insert_sql, [tuple(adapt(v) for v in row) for row in rows])
        dest.commit()
        total += len(rows)
        if progress:
            progress(f"  {table}: {total:,} rows...")
    cursor.close()
    return total
