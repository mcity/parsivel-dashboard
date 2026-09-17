"""Tests for scripts/ingest.py (delta apply) and the export side of sync_to_aws.py."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ingest  # noqa: E402
import sync_to_aws  # noqa: E402


def _ott_rows(start_minute: int, n: int, rain: float = 0.0):
    return [
        (f"2026-01-01 00:{m:02d}:00.000000", "SN1", rain, m)
        for m in range(start_minute, start_minute + n)
    ]


def _make_main(path: Path, rows) -> None:
    c = sqlite3.connect(path)
    c.execute(
        'CREATE TABLE "parsivel_OTT" ("cpuTimestamp" TEXT, "sensorSerNo" TEXT, '
        '"rainIntensity" REAL, "seqNo" INTEGER)'
    )
    c.executemany('INSERT INTO "parsivel_OTT" VALUES (?, ?, ?, ?)', rows)
    c.commit()
    c.close()


def _make_delta(path: Path, table: str, key: str, watermark, mode: str, rows, cols_sql: str) -> None:
    d = sqlite3.connect(path)
    d.execute(f'CREATE TABLE "{table}" ({cols_sql})')
    placeholders = ", ".join("?" for _ in rows[0]) if rows else "?"
    if rows:
        d.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    d.commit()
    ingest.write_meta(d, table, key, watermark, mode, len(rows))
    d.close()


OTT_COLS = '"cpuTimestamp" TEXT, "sensorSerNo" TEXT, "rainIntensity" REAL, "seqNo" INTEGER'


def test_state_reports_max_key_and_missing_tables(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 3))
    conn = sqlite3.connect(main)
    state = ingest.read_state(conn)
    assert state["parsivel_OTT"] == "2026-01-01 00:02:00.000000"
    assert state["parsivel_ved_histogram"] is None
    assert set(state) == set(ingest.KEY_COLUMNS)


def test_append_delta_adds_rows_and_is_idempotent(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 3))
    delta = tmp_path / "delta.db"
    watermark = "2026-01-01 00:02:00.000000"
    _make_delta(delta, "parsivel_OTT", "cpuTimestamp", watermark, "append", _ott_rows(3, 2), OTT_COLS)

    conn = sqlite3.connect(main, isolation_level=None)
    stats = ingest.apply_delta(conn, delta)
    assert stats["parsivel_OTT"] == {"mode": "append", "deleted": 0, "inserted": 2}
    assert conn.execute('SELECT COUNT(*) FROM "parsivel_OTT"').fetchone()[0] == 5

    # Re-applying the same delta replaces, rather than duplicates, the rows above the watermark.
    stats = ingest.apply_delta(conn, delta)
    assert stats["parsivel_OTT"] == {"mode": "append", "deleted": 2, "inserted": 2}
    assert conn.execute('SELECT COUNT(*) FROM "parsivel_OTT"').fetchone()[0] == 5
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    # Index from INDEXES was created.
    names = {r[1] for r in conn.execute('PRAGMA index_list("parsivel_OTT")')}
    assert "ix_parsivel_OTT_cpuTimestamp" in names


def test_append_creates_missing_table(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 1))
    delta = tmp_path / "delta.db"
    _make_delta(
        delta, "parsivel_ved_histogram", "histogram_id", None, "append",
        [(1,), (2,)], '"histogram_id" INTEGER',
    )
    conn = sqlite3.connect(main, isolation_level=None)
    stats = ingest.apply_delta(conn, delta)
    assert stats["parsivel_ved_histogram"]["inserted"] == 2
    assert ingest.read_state(conn)["parsivel_ved_histogram"] == 2


def test_replace_mode_rebuilds_table(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 10))
    delta = tmp_path / "delta.db"
    _make_delta(delta, "parsivel_OTT", "cpuTimestamp", None, "replace", _ott_rows(0, 2), OTT_COLS)
    conn = sqlite3.connect(main, isolation_level=None)
    ingest.apply_delta(conn, delta)
    assert conn.execute('SELECT COUNT(*) FROM "parsivel_OTT"').fetchone()[0] == 2


def test_row_count_mismatch_rolls_back(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 3))
    delta = tmp_path / "delta.db"
    _make_delta(delta, "parsivel_OTT", "cpuTimestamp", None, "append", _ott_rows(3, 2), OTT_COLS)
    d = sqlite3.connect(delta)
    d.execute(f'UPDATE "{ingest.META_TABLE}" SET row_count = 99')
    d.commit()
    d.close()

    conn = sqlite3.connect(main, isolation_level=None)
    with pytest.raises(ValueError, match="claims 99"):
        ingest.apply_delta(conn, delta)
    assert conn.execute('SELECT COUNT(*) FROM "parsivel_OTT"').fetchone()[0] == 3


def test_rejects_file_without_meta(tmp_path):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 1))
    bogus = tmp_path / "bogus.db"
    sqlite3.connect(bogus).execute("CREATE TABLE x (a)").connection.close()
    conn = sqlite3.connect(main, isolation_level=None)
    with pytest.raises(ValueError, match="not a sync delta"):
        ingest.apply_delta(conn, bogus)


def test_cli_state_and_import(tmp_path, capsys):
    main = tmp_path / "main.db"
    _make_main(main, _ott_rows(0, 2))
    delta = tmp_path / "delta.db"
    _make_delta(delta, "parsivel_OTT", "cpuTimestamp", "2026-01-01 00:01:00.000000", "append",
                _ott_rows(2, 1), OTT_COLS)

    assert ingest.main(["--db", str(main), "import", str(delta)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tables"]["parsivel_OTT"]["inserted"] == 1

    assert ingest.main(["--db", str(main), "state"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["parsivel_OTT"] == "2026-01-01 00:02:00.000000"


def test_resolve_db_path_from_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////app/data/parsivel.db")
    assert ingest.resolve_db_path(None) == Path("/app/data/parsivel.db")
    assert ingest.resolve_db_path("x.db") == Path("x.db")


# --- export side -----------------------------------------------------------

def _fake_source(tmp_path: Path) -> sqlite3.Connection:
    """SQLite standing in for SQL Server: an attached schema named `dbo` and
    [bracket] identifiers, both of which SQLite accepts."""
    src = sqlite3.connect(":memory:")
    src.execute(f"ATTACH DATABASE '{tmp_path / 'dbo.db'}' AS dbo")
    src.execute('CREATE TABLE dbo."parsivel_OTT" ("cpuTimestamp" TEXT, "rainIntensity" REAL)')
    src.executemany(
        'INSERT INTO dbo."parsivel_OTT" VALUES (?, ?)',
        [(f"2026-01-01 00:{m:02d}:00.000000", float(m)) for m in range(5)],
    )
    src.execute('CREATE TABLE dbo."parsivel_ved_histogram" ("histogram_id" INTEGER)')
    src.executemany('INSERT INTO dbo."parsivel_ved_histogram" VALUES (?)', [(i,) for i in range(1, 8)])
    src.commit()
    return src


def test_export_delta_selects_rows_above_watermark(tmp_path, monkeypatch):
    # The real code binds a datetime for cpuTimestamp; SQLite compares it as text
    # in ISO form, so feed a watermark whose text form matches the stored rows.
    monkeypatch.setattr(
        sync_to_aws, "_source_watermark_param",
        lambda key, wm: None if wm is None else (str(wm) if key == "cpuTimestamp" else int(wm)),
    )
    src = _fake_source(tmp_path)
    state = {"parsivel_OTT": "2026-01-01 00:02:00.000000", "parsivel_ved_histogram": 5}
    delta = tmp_path / "delta.db"
    counts = sync_to_aws.export_delta(
        src, delta, ["parsivel_OTT", "parsivel_ved_histogram"], state, full=False
    )
    assert counts == {"parsivel_OTT": 2, "parsivel_ved_histogram": 2}

    d = sqlite3.connect(delta)
    meta = {r[0]: r for r in d.execute(
        f'SELECT table_name, key_column, watermark, mode, row_count FROM "{ingest.META_TABLE}"'
    )}
    assert meta["parsivel_OTT"][1:] == ("cpuTimestamp", state["parsivel_OTT"], "append", 2)
    assert meta["parsivel_ved_histogram"][2] == 5
    # int() because the fake SQLite source carries no column types (pyodbc does).
    assert [int(r[0]) for r in d.execute('SELECT "histogram_id" FROM "parsivel_ved_histogram" ORDER BY 1')] == [6, 7]


def test_export_delta_full_uses_replace_mode(tmp_path):
    src = _fake_source(tmp_path)
    delta = tmp_path / "delta.db"
    counts = sync_to_aws.export_delta(src, delta, ["parsivel_OTT"], {"parsivel_OTT": "x"}, full=True)
    assert counts == {"parsivel_OTT": 5}
    d = sqlite3.connect(delta)
    mode, wm = d.execute(f'SELECT mode, watermark FROM "{ingest.META_TABLE}"').fetchone()
    assert (mode, wm) == ("replace", None)


def test_watermark_param_conversion():
    ts = sync_to_aws._source_watermark_param("cpuTimestamp", "2026-07-29 06:48:52.000000")
    assert ts.year == 2026 and ts.second == 52
    assert sync_to_aws._source_watermark_param("histogram_id", 164469) == 164469
    assert sync_to_aws._source_watermark_param("histogram_id", None) is None


def test_load_env_file_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / ".sync.env"
    f.write_text('A=1\n# comment\nB="two"\nC=3\n', encoding="utf-8")
    monkeypatch.setenv("C", "keep")
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    sync_to_aws.load_env_file(f)
    import os
    assert os.environ["A"] == "1"
    assert os.environ["B"] == "two"
    assert os.environ["C"] == "keep"
