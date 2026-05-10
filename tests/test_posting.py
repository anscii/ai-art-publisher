from unittest.mock import MagicMock, patch

import httpx
import respx

IG_BASE = "https://graph.instagram.com/v25.0"
FB_BASE = "https://graph.facebook.com/v25.0"


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


def _mock_settings(token="TOKEN", channel="@ch", base="https://pub.r2.dev", fb=False):
    s = MagicMock()
    s.telegram_bot_token = token
    s.telegram_channel_id = channel
    s.r2_public_base_url = base
    s.instagram_access_token = "IG_TOKEN"
    s.instagram_user_id = "IG_USER"
    s.facebook_page_id = "FB_PAGE_ID" if fb else None
    s.facebook_page_access_token = "FB_PAGE_TOKEN" if fb else None
    return s


def _mock_ig_single():
    respx.post(f"{IG_BASE}/IG_USER/media").mock(return_value=httpx.Response(200, json={"id": "c1"}))
    respx.get(f"{IG_BASE}/c1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{IG_BASE}/IG_USER/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "p1"})
    )


def _mock_fb_single():
    respx.post(f"{FB_BASE}/FB_PAGE_ID/photos").mock(
        return_value=httpx.Response(200, json={"id": "ph1"})
    )


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


# ── Instagram ─────────────────────────────────────────────────────────────────


@respx.mock
def test_post_instagram_success(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        _mock_ig_single()
        resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_instagram_marks_images_posted(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        _mock_ig_single()
        client.post(f"/api/series/{sid}/post/instagram")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"


@respx.mock
def test_post_instagram_sets_timestamp(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        _mock_ig_single()
        client.post(f"/api/series/{sid}/post/instagram")
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_instagram_at"] is not None
    assert detail["posted_to_facebook_at"] is None


@respx.mock
def test_post_instagram_error_appended_to_notes(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post(f"{IG_BASE}/IG_USER/media").mock(
            return_value=httpx.Response(200, json={"error": {"message": "Invalid token"}})
        )
        resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json()["success"] is False
    detail = client.get(f"/api/series/{sid}").json()
    assert "Invalid token" in detail["notes"]


# ── Facebook Page (posted alongside Instagram) ────────────────────────────────


@respx.mock
def test_post_instagram_with_facebook_success(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings(fb=True)):
        _mock_ig_single()
        _mock_fb_single()
        resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json()["success"] is True
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_instagram_at"] is not None
    assert detail["posted_to_facebook_at"] is not None


@respx.mock
def test_post_instagram_facebook_skipped_when_no_page_id(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings(fb=False)):
        _mock_ig_single()
        resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json()["success"] is True
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_facebook_at"] is None


@respx.mock
def test_post_instagram_facebook_error_does_not_fail_post(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings(fb=True)):
        _mock_ig_single()
        respx.post(f"{FB_BASE}/FB_PAGE_ID/photos").mock(
            return_value=httpx.Response(200, json={"error": {"message": "FB error"}})
        )
        resp = client.post(f"/api/series/{sid}/post/instagram")
    assert resp.json()["success"] is True
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_instagram_at"] is not None
    assert detail["posted_to_facebook_at"] is None


# ── Both ──────────────────────────────────────────────────────────────────────


@respx.mock
def test_post_both_success(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        _mock_ig_single()
        resp = client.post(f"/api/series/{sid}/post/both")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_both_marks_images_posted(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        _mock_ig_single()
        client.post(f"/api/series/{sid}/post/both")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(img["status"] == "posted" for img in detail["images"])
    assert detail["status"] == "posted"
    assert detail["posted_to_telegram_at"] is not None
    assert detail["posted_to_instagram_at"] is not None


@respx.mock
def test_post_both_with_facebook(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings(fb=True)):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        _mock_ig_single()
        _mock_fb_single()
        resp = client.post(f"/api/series/{sid}/post/both")
    assert resp.json()["success"] is True
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["posted_to_facebook_at"] is not None


@respx.mock
def test_post_both_telegram_error(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": False, "description": "TG failed"})
        )
        _mock_ig_single()
        resp = client.post(f"/api/series/{sid}/post/both")
    assert resp.json()["success"] is False
    detail = client.get(f"/api/series/{sid}").json()
    assert "TG failed" in detail["notes"]


@respx.mock
def test_post_both_instagram_error(client):
    sid = _setup(client)
    with patch("app.routers.posting.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        respx.post(f"{IG_BASE}/IG_USER/media").mock(
            return_value=httpx.Response(200, json={"error": {"message": "IG failed"}})
        )
        resp = client.post(f"/api/series/{sid}/post/both")
    assert resp.json()["success"] is False
    detail = client.get(f"/api/series/{sid}").json()
    assert "IG failed" in detail["notes"]
