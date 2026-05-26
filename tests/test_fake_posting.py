"""Tests for FAKE_POSTING mode — verifies no real HTTP calls are made and that
the response messages and DB state still reflect the full normal posting flow."""

import logging
from unittest.mock import MagicMock, patch

import respx

from tests.test_posting import _mock_settings, _setup


def _fake_cfg():
    cfg = MagicMock()
    cfg.fake_posting = True
    return cfg


# ── Telegram ──────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_telegram_returns_sending_immediately(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/posts/{pid}/post")
    # Endpoint always returns "Sending…"; actual result is set by background task.
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Sending…"}


@respx.mock
def test_fake_telegram_marks_post_posted(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None


@respx.mock
def test_fake_telegram_logs(client, caplog):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            with caplog.at_level(logging.INFO, logger="app.routers.posts"):
                client.post(f"/api/posts/{pid}/post")
    assert any("[FAKE]" in r.message and "telegram" in r.message for r in caplog.records)


# ── Instagram ─────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_instagram_returns_sending_immediately(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json() == {"success": True, "message": "Sending…"}


@respx.mock
def test_fake_instagram_marks_post_posted(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None


# ── Pinterest ──────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_pinterest_returns_sending_immediately(client):
    _, pid = _setup(client, "pinterest")
    with patch(
        "app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=True)
    ):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json() == {"success": True, "message": "Sending…"}


@respx.mock
def test_fake_pinterest_marks_post_posted(client):
    _, pid = _setup(client, "pinterest")
    with patch(
        "app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=True)
    ):
        with patch("app.routers.posts.get_config", return_value=_fake_cfg()):
            client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None
