from datetime import datetime, timedelta

import pytest

from app.models import ParsivelOTT


def test_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


# def test_example_returns_latest_row_with_fill_nulled(client):
#     r = client.get("/api/example")
#     assert r.status_code == 200
#     body = r.get_json()

#     # Second seeded row (12:01) is newer than the first (12:00).
#     assert body["cpuTimestamp"].startswith("2025-01-01T12:01:00")
#     # rainIntensity=-9.999 in fixture -> nulled in response.
#     assert body["rainIntensity"] is None
#     # sensorStatus=1 decodes to "screens dirty".
#     assert body["sensorStatus"] == 1
#     assert body["sensorStatusText"] == "screens dirty"


def test_series_basic_shape(client):
    r = client.get("/api/measurements/ott/series")
    assert r.status_code == 200
    body = r.get_json()

    # Two seeded rows 1 minute apart -> 60s buckets, points sorted by time.
    assert body["bucketSeconds"] == 60
    buckets = [p["bucket"] for p in body["points"]]
    assert buckets == sorted(buckets)
    assert len(buckets) == 2

    # First bucket keeps its real intensity; second's -9.999 fill is nulled.
    assert body["points"][0]["peakIntensity"] == pytest.approx(0.5)
    assert body["points"][1]["peakIntensity"] is None


def test_series_rollover_correction(client, session_factory):
    """A negative ΔrainAmt is treated as a 300 mm accumulator wrap, not a drop."""
    s = session_factory()
    base = datetime(2030, 1, 1, 0, 0, 0)
    amts = [299.0, 299.8, 0.5, 1.0]        # wraps between the 2nd and 3rd sample
    intensities = [1.0, 2.0, 3.0, 0.5]
    s.add_all([
        ParsivelOTT(
            cpuTimestamp=base + timedelta(minutes=i),
            rainAmt=a,
            rainIntensity=it,
            wxCode=61,
            sensorStatus=0,
        )
        for i, (a, it) in enumerate(zip(amts, intensities))
    ])
    s.commit()
    s.close()

    r = client.get(
        "/api/measurements/ott/series",
        query_string={
            "start": "2030-01-01T00:00:00",
            "end": "2030-01-01T01:00:00",
            "bucket": "86400",  # one day -> all four samples in one bucket
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["bucketSeconds"] == 86400
    assert len(body["points"]) == 1

    p = body["points"][0]
    # Increments: (no predecessor -> 0) + 0.8 + (0.5-299.8+300=0.7) + 0.5 = 2.0
    # Without correction the wrap would contribute -299.3 and wreck the total.
    assert p["rainMm"] == pytest.approx(2.0, abs=1e-6)
    assert p["cumulative"] == pytest.approx(2.0, abs=1e-6)
    assert p["peakIntensity"] == pytest.approx(3.0)
    assert p["wxCode"] == 61


def test_series_empty_range_returns_empty(client):
    r = client.get(
        "/api/measurements/ott/series",
        query_string={"start": "1990-01-01T00:00:00", "end": "1990-01-02T00:00:00"},
    )
    assert r.status_code == 200
    assert r.get_json()["points"] == []


def test_series_chart_view_rejects_range_over_1_year(client):
    r = client.get(
        "/api/measurements/ott/series",
        query_string={
            "start": "2020-01-01T00:00:00",
            "end": "2021-01-02T00:00:00",  # 367 days
            "view": "chart",
        },
    )
    assert r.status_code == 400
    body = r.get_json()
    assert "exceeds 1 year maximum" in (body.get("description") or body.get("message", ""))


def test_series_table_view_allows_range_over_1_year(client):
    r = client.get(
        "/api/measurements/ott/series",
        query_string={
            "start": "2020-01-01T00:00:00",
            "end": "2021-01-02T00:00:00",  # 367 days
            "view": "table",
        },
    )
    # Table view should succeed (empty points since no data in those dates)
    assert r.status_code == 200
    assert r.get_json()["points"] == []
