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
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    ).json()["id"]
    # queue the image so posting proceeds
    client.patch(f"/api/images/{img_id}/status", json={"status": "queued"})
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
def test_post_telegram_marks_images_posted(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.post(f"/api/series/{sid}/post/telegram")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"


@respx.mock
def test_post_telegram_partial_posted(client):
    sid = client.post(
        "/api/series", json={"title": "T", "description_ru": "R", "description_en": "E"}
    ).json()["id"]
    client.put(f"/api/series/{sid}", json={"tags_telegram": [], "tags_instagram": []})
    img1 = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/a.jpg", "original_filename": "a.jpg"},
    ).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/b.jpg", "original_filename": "b.jpg"},
    )
    client.patch(f"/api/images/{img1}/status", json={"status": "queued"})
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.post(f"/api/series/{sid}/post/telegram")
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "partial_posted"


@respx.mock
def test_post_no_queued_returns_400(client):
    sid = client.post(
        "/api/series", json={"title": "T", "description_ru": "R", "description_en": "E"}
    ).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    resp = client.post(f"/api/series/{sid}/post/telegram")
    assert resp.status_code == 400
    assert "queued" in resp.json()["detail"]


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
