from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch


def _make_post(client, platform="telegram"):
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": [platform],
            "title": "T",
            "description_telegram": "R",
            "description_other": "E",
            "image_ids": [img_id],
        },
    ).json()
    return sid, posts[0]["id"]


def test_schedule_sets_status(client):
    _, pid = _make_post(client)
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = client.post(f"/api/posts/{pid}/schedule", json={"datetime_utc": future})
    assert resp.status_code == 200
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "scheduled"
    assert post["scheduled_at"] is not None


def test_cancel_schedule(client):
    _, pid = _make_post(client)
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    client.post(f"/api/posts/{pid}/schedule", json={"datetime_utc": future})
    resp = client.delete(f"/api/posts/{pid}/schedule")
    assert resp.status_code == 200
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "draft"
    assert post["scheduled_at"] is None


def test_queue_sorted_by_datetime(client):
    now = datetime.now(UTC)
    _, p1 = _make_post(client)
    _, p2 = _make_post(client)
    client.post(
        f"/api/posts/{p1}/schedule",
        json={"datetime_utc": (now + timedelta(hours=2)).isoformat()},
    )
    client.post(
        f"/api/posts/{p2}/schedule",
        json={"datetime_utc": (now + timedelta(hours=1)).isoformat()},
    )
    data = client.get("/api/queue").json()
    post_ids = [item["post_id"] for item in data]
    assert post_ids.index(p2) < post_ids.index(p1)


def test_queue_returns_correct_fields(client):
    sid, pid = _make_post(client, "telegram")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    client.post(f"/api/posts/{pid}/schedule", json={"datetime_utc": future})
    data = client.get("/api/queue").json()
    assert len(data) == 1
    item = data[0]
    assert item["post_id"] == pid
    assert item["series_id"] == sid
    assert item["platform"] == "telegram"
    assert item["scheduled_at"] is not None


def test_cancel_non_scheduled_returns_400(client):
    _, pid = _make_post(client)
    resp = client.delete(f"/api/posts/{pid}/schedule")
    assert resp.status_code == 400


def _fake_config(secret="test-secret"):
    cfg = MagicMock()
    cfg.scheduler_secret = secret
    return cfg


def test_run_scheduler_no_token(client):
    with patch("app.routers.scheduling.get_config", return_value=_fake_config()):
        resp = client.post("/internal/run-scheduler")
    assert resp.status_code == 401


def test_run_scheduler_wrong_token(client):
    with patch("app.routers.scheduling.get_config", return_value=_fake_config()):
        resp = client.post("/internal/run-scheduler", headers={"X-Scheduler-Token": "wrong"})
    assert resp.status_code == 401


def test_run_scheduler_correct_token(client):
    with (
        patch("app.routers.scheduling.get_config", return_value=_fake_config()),
        patch("app.routers.scheduling.run_scheduled_posts") as mock_run,
    ):
        resp = client.post("/internal/run-scheduler", headers={"X-Scheduler-Token": "test-secret"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_run.assert_called_once()


def test_run_scheduler_empty_secret_rejects(client):
    with patch("app.routers.scheduling.get_config", return_value=_fake_config(secret="")):
        resp = client.post("/internal/run-scheduler", headers={"X-Scheduler-Token": ""})
    assert resp.status_code == 401
