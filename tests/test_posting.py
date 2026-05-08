from unittest.mock import MagicMock, patch

import httpx
import respx


def _setup(client):
    sid = client.post(
        "/api/series",
        json={
            "title": "Dragon Forest",
            "description_ru": "Мистический лес",
            "description_en": "A mystical forest",
        },
    ).json()["id"]
    client.put(
        f"/api/series/{sid}",
        json={
            "tags_telegram": ["#арт"],
            "tags_instagram": ["#art"],
        },
    )
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    return sid


def _mock_settings(token="TOKEN", channel="@ch", base="https://pub.r2.dev"):
    s = MagicMock()
    s.telegram_bot_token = token
    s.telegram_channel_id = channel
    s.r2_public_base_url = base
    s.instagram_access_token = "IG_TOKEN"
    s.instagram_user_id = "IG_USER"
    return s


@respx.mock
def test_post_telegram_success(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        resp = client.post(f"/api/series/{sid}/post/telegram")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_telegram_error_appended_to_notes(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": False, "description": "Bad request"})
        )
        resp = client.post(f"/api/series/{sid}/post/telegram")
    assert resp.json()["success"] is False
    detail = client.get(f"/api/series/{sid}").json()
    assert "Bad request" in detail["notes"]
