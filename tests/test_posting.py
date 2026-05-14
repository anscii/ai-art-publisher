"""Tests for immediate posting via /api/posts/{id}/post."""

from unittest.mock import MagicMock, patch

import httpx
import respx

from app.routers.posts import execute_post

IG_BASE = "https://graph.instagram.com/v25.0"
FB_BASE = "https://graph.facebook.com/v25.0"


def _setup(client, platform="telegram"):
    """Create series + image + post draft; return (series_id, post_id)."""
    sid = client.post("/api/series", json={"title": "Dragon Forest"}).json()["id"]
    client.put(
        f"/api/series/{sid}",
        json={
            "description_ru": "Мистический лес",
            "description_en": "A mystical forest",
            "tags_telegram": ["#арт"],
            "tags_instagram": ["#art"],
        },
    )
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    ).json()["id"]
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": [platform],
            "title": "Dragon Forest",
            "description_telegram": "Мистический лес",
            "description_other": "A mystical forest",
            "tags_telegram": ["#арт"],
            "tags_other": ["#art"],
            "image_ids": [img_id],
        },
    ).json()
    return sid, posts[0]["id"]


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


# ── Telegram ──────────────────────────────────────────────────────────────────


@respx.mock
def test_post_telegram_success(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_telegram_marks_post_posted(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None


@respx.mock
def test_post_telegram_error_sets_failed_status(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": False, "description": "Bad request"})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is False
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "failed"
    assert "Bad request" in post["error_message"]


@respx.mock
def test_post_duplicate_protection(client):
    _, pid = _setup(client, "telegram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.post(f"/api/posts/{pid}/post")
        resp2 = client.post(f"/api/posts/{pid}/post")
    assert resp2.json()["success"] is False
    assert "Already posted" in resp2.json()["message"]


@respx.mock
def test_execute_post_telegram_duplicate_protection_via_status(client, db):
    """Scheduler calls execute_post directly; Telegram has no external_post_id.
    Protection must rely on post.status == 'posted', not external_post_id."""
    _, pid = _setup(client, "telegram")
    # First post succeeds
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post("https://api.telegram.org/botTOKEN/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.post(f"/api/posts/{pid}/post")

    # Fetch the Post ORM object and verify external_post_id is None (Telegram)
    from app.models import Post

    post = db.get(Post, pid)
    assert post.status == "posted"
    assert post.external_post_id is None  # confirms the protection can't rely on this

    # Call execute_post directly (scheduler path) — must be blocked by status check
    result = execute_post(post, db, _mock_settings())
    assert result.success is False
    assert "Already posted" in result.message


# ── Instagram ─────────────────────────────────────────────────────────────────


@respx.mock
def test_post_instagram_success(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        _mock_ig_single()
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_instagram_marks_post_posted(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        _mock_ig_single()
        client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None
    assert post["external_post_id"] == "p1"


@respx.mock
def test_post_instagram_error_sets_failed(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings()):
        respx.post(f"{IG_BASE}/IG_USER/media").mock(
            return_value=httpx.Response(200, json={"error": {"message": "Invalid token"}})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is False
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "failed"
    assert "Invalid token" in post["error_message"]


# ── Facebook (cross-posted alongside Instagram) ───────────────────────────────


@respx.mock
def test_post_instagram_with_facebook_success(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(fb=True)):
        _mock_ig_single()
        _mock_fb_single()
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True


@respx.mock
def test_post_instagram_facebook_skipped_when_no_page_id(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(fb=False)):
        _mock_ig_single()
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"


@respx.mock
def test_post_instagram_facebook_error_does_not_fail_post(client):
    _, pid = _setup(client, "instagram")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(fb=True)):
        _mock_ig_single()
        respx.post(f"{FB_BASE}/FB_PAGE_ID/photos").mock(
            return_value=httpx.Response(200, json={"error": {"message": "FB error"}})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"


# ── Facebook direct ───────────────────────────────────────────────────────────


@respx.mock
def test_post_facebook_direct(client):
    _, pid = _setup(client, "facebook")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(fb=True)):
        _mock_fb_single()
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["external_post_id"] == "ph1"
