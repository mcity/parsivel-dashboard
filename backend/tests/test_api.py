def test_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_example_returns_latest_row_with_fill_nulled(client):
    r = client.get("/api/example")
    assert r.status_code == 200
    body = r.get_json()

    # Second seeded row (12:01) is newer than the first (12:00).
    assert body["cpuTimestamp"].startswith("2025-01-01T12:01:00")
    # rainIntensity=-9.999 in fixture -> nulled in response.
    assert body["rainIntensity"] is None
    # sensorStatus=1 decodes to "screens dirty".
    assert body["sensorStatus"] == 1
    assert body["sensorStatusText"] == "screens dirty"
