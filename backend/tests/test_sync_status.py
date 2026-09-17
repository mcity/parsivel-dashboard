"""/api/sync/status and the sync-log side of scripts/ingest.py."""

import sqlite3
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ingest  # noqa: E402


def test_sync_status_null_without_log_table(client):
    r = client.get("/api/sync/status")
    assert r.status_code == 200
    assert r.get_json() == {"lastSyncAt": None, "rowsInserted": None}


def test_sync_status_returns_latest_entry(client, session_factory):
    s = session_factory()
    s.execute(text(
        "CREATE TABLE _sync_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "synced_at TEXT NOT NULL, rows_inserted INTEGER NOT NULL, source TEXT)"
    ))
    s.execute(text(
        "INSERT INTO _sync_log (synced_at, rows_inserted, source) VALUES "
        "('2026-09-17T20:49:44+00:00', 291369, 'delta-1.db'), "
        "('2026-09-18T10:00:03+00:00', 0, NULL)"
    ))
    s.commit()
    s.close()

    r = client.get("/api/sync/status")
    assert r.status_code == 200
    assert r.get_json() == {"lastSyncAt": "2026-09-18T10:00:03+00:00", "rowsInserted": 0}


def test_mark_and_import_append_to_sync_log(tmp_path, capsys):
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db, isolation_level=None)
    assert ingest.read_last_sync(conn) is None

    assert ingest.main(["--db", str(db), "mark"]) == 0
    capsys.readouterr()
    last = ingest.read_last_sync(conn)
    assert last["rows_inserted"] == 0 and last["source"] is None
    assert last["synced_at"].endswith("+00:00")

    # An import logs the delta name and the number of rows it inserted.
    delta = tmp_path / "delta-x.db"
    d = sqlite3.connect(delta)
    d.execute('CREATE TABLE "parsivel_ved_histogram" ("histogram_id" INTEGER)')
    d.executemany('INSERT INTO "parsivel_ved_histogram" VALUES (?)', [(1,), (2,), (3,)])
    d.commit()
    ingest.write_meta(d, "parsivel_ved_histogram", "histogram_id", None, "append", 3)
    d.close()
    stats = ingest.apply_delta(conn, delta)
    assert "synced_at" in stats["_sync"]
    last = ingest.read_last_sync(conn)
    assert last == {"synced_at": stats["_sync"]["synced_at"], "rows_inserted": 3, "source": "delta-x.db"}
    # The log itself is not a synced table.
    assert "_sync_log" not in ingest.read_state(conn)
