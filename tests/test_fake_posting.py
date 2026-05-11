"""Tests for FAKE_POSTING mode — verifies no real HTTP calls are made and that
the response messages and DB state still reflect the full normal posting flow."""

from unittest.mock import MagicMock, patch

import respx

from tests.test_posting import _mock_settings, _setup


def _fake_cfg():
    cfg = MagicMock()
    cfg.fake_posting = True
    return cfg


# ── Telegram ──────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_telegram_returns_fake_message(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/series/{sid}/post/telegram")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "[FAKE] Posted to telegram"}


@respx.mock
def test_fake_telegram_marks_images_and_series_posted(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            client.post(f"/api/series/{sid}/post/telegram")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"
    assert detail["posted_to_telegram_at"] is not None


@respx.mock
def test_fake_telegram_logs(client, caplog):
    import logging

    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            with caplog.at_level(logging.INFO, logger="app.routers.posting"):
                client.post(f"/api/series/{sid}/post/telegram")
    assert any("[FAKE]" in r.message and "Telegram" in r.message for r in caplog.records)
    assert any(sid in r.message for r in caplog.records)


# ── Instagram ─────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_instagram_returns_fake_message(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json() == {"success": True, "message": "[FAKE] Posted to instagram"}


@respx.mock
def test_fake_instagram_marks_images_and_series_posted(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            client.post(f"/api/series/{sid}/post/instagram")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"
    assert detail["posted_to_instagram_at"] is not None


@respx.mock
def test_fake_instagram_with_facebook_sets_both_timestamps(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings(fb=True)):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json()["success"] is True
    assert "[FAKE]" in resp.json()["message"]
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_instagram_at"] is not None
    assert detail["posted_to_facebook_at"] is not None


# ── Both ──────────────────────────────────────────────────────────────────────


@respx.mock
def test_fake_both_returns_fake_message(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            resp = client.post(f"/api/series/{sid}/post/both")
    assert resp.json() == {"success": True, "message": "[FAKE] Posted to both"}


@respx.mock
def test_fake_both_marks_images_and_both_timestamps(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        with patch("app.routers.posting.get_config", return_value=_fake_cfg()):
            client.post(f"/api/series/{sid}/post/both")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"
    assert detail["posted_to_telegram_at"] is not None
    assert detail["posted_to_instagram_at"] is not None
