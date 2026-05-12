from datetime import UTC, datetime, timedelta


def _series(client, status="approved"):
    sid = client.post("/api/series", json={"title": "S", "status": status}).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    )
    return sid


def test_schedule_sets_status(client):
    sid = _series(client)
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = client.post(
        f"/api/series/{sid}/schedule",
        json={
            "datetime_utc": future,
            "targets": ["telegram"],
        },
    )
    assert resp.status_code == 200
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "scheduled"
    assert detail["scheduled_targets"] == ["telegram"]


def test_cancel_schedule(client):
    sid = _series(client)
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    client.post(
        f"/api/series/{sid}/schedule", json={"datetime_utc": future, "targets": ["telegram"]}
    )
    client.delete(f"/api/series/{sid}/schedule")
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "approved"
    assert detail["scheduled_at"] is None


def test_queue_sorted_by_datetime(client):
    now = datetime.now(UTC)
    s1 = _series(client)
    s2 = _series(client)
    client.post(
        f"/api/series/{s1}/schedule",
        json={"datetime_utc": (now + timedelta(hours=2)).isoformat(), "targets": ["telegram"]},
    )
    client.post(
        f"/api/series/{s2}/schedule",
        json={"datetime_utc": (now + timedelta(hours=1)).isoformat(), "targets": ["instagram"]},
    )
    data = client.get("/api/queue").json()
    assert data[0]["series_id"] == s2
    assert data[1]["series_id"] == s1
