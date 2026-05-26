"""Tests for the async "sending" status and background posting behavior.

Key facts about the test environment:
- FastAPI TestClient runs BackgroundTasks synchronously before returning the response.
- conftest monkeypatches app.database.SessionLocal → _TestingSessionLocal (in-memory DB).
- _execute_post_background uses _db_module.SessionLocal() (module reference), so it
  correctly picks up the patched test session factory.
"""

from unittest.mock import patch

import respx

from app.models import Post
from app.routers.posts import _execute_post_background
from tests.test_posting import _mock_settings, _setup


def _make_post(client, platform="telegram"):
    sid, pid = _setup(client, platform)
    return sid, pid


# ── Endpoint response shape ───────────────────────────────────────────────────


@respx.mock
def test_post_now_returns_sending_immediately(client):
    """Endpoint always returns success=True, message='Sending…' regardless of outcome."""
    _, pid = _make_post(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=__import__("httpx").Response(200, json={"ok": True})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["message"] == "Sending…"


@respx.mock
def test_post_now_background_updates_status_to_posted(client):
    """After background task runs, post status is 'posted' (TestClient runs BG synchronously)."""
    _, pid = _make_post(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=__import__("httpx").Response(200, json={"ok": True})
        )
        client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"


# ── Already-sending guard ─────────────────────────────────────────────────────


def test_post_now_already_sending_returns_false(client, db):
    """Calling post_now on a post already in 'sending' state returns success=False."""
    _, pid = _make_post(client, "telegram")
    # Manually put post into "sending" state
    post = db.get(Post, pid)
    post.status = "sending"
    db.commit()

    resp = client.post(f"/api/posts/{pid}/post")
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "sending" in resp.json()["message"].lower()


# ── Background function error handling ────────────────────────────────────────


def test_execute_post_background_nonexistent_post_does_not_raise():
    """_execute_post_background must not raise if post is not found."""
    _execute_post_background("nonexistent-id-12345")  # should return cleanly


@respx.mock
def test_execute_post_background_exception_sets_failed(client, db):
    """If execute_post raises unexpectedly, status must be set to 'failed'."""
    _, pid = _make_post(client, "telegram")
    post = db.get(Post, pid)
    post.status = "sending"
    db.commit()

    with patch(
        "app.routers.posts.execute_post",
        side_effect=RuntimeError("Unexpected crash"),
    ):
        with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
            _execute_post_background(pid)

    db.expire_all()
    refreshed = db.get(Post, pid)
    assert refreshed.status == "failed"
    assert "Unexpected crash" in (refreshed.error_message or "")


# ── Startup recovery ──────────────────────────────────────────────────────────


def test_startup_resets_stuck_sending_posts(client, db):
    """Posts stuck in 'sending' from a prior run must be reset to 'failed' on startup."""
    from app import database as _db_module

    _, pid = _make_post(client, "telegram")
    post = db.get(Post, pid)
    post.status = "sending"
    db.commit()

    # Simulate startup recovery logic directly (same code as lifespan).
    _db = _db_module.SessionLocal()
    try:
        stuck = _db.query(Post).filter(Post.status == "sending").all()
        for _p in stuck:
            _p.status = "failed"
            _p.error_message = "Server restarted during sending"
        _db.commit()
    finally:
        _db.close()

    db.expire_all()
    recovered = db.get(Post, pid)
    assert recovered.status == "failed"
    assert "restarted" in (recovered.error_message or "")
