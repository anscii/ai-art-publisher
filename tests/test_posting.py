"""Tests for immediate posting via /api/posts/{id}/post."""

import json
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


PT_BASE = "https://api.pinterest.com/v5"


def _mock_settings(token="TOKEN", channel="@ch", base="https://pub.r2.dev", fb=False, pinterest=False):
    s = MagicMock()
    s.telegram_bot_token = token
    s.telegram_channel_id = channel
    s.r2_public_base_url = base
    s.instagram_access_token = "IG_TOKEN"
    s.instagram_user_id = "IG_USER"
    s.facebook_page_id = "FB_PAGE_ID" if fb else None
    s.facebook_page_access_token = "FB_PAGE_TOKEN" if fb else None
    s.pinterest_access_token = "PT_TOKEN" if pinterest else None
    s.pinterest_default_board_id = "999888777" if pinterest else None
    s.pinterest_board_map = '{"Fantasy Art": "111222333"}' if pinterest else None
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


# ── Pinterest service unit tests ──────────────────────────────────────────────


@respx.mock
def test_pinterest_service_post_pins_single():
    from app.services.pinterest import PinterestService

    svc = PinterestService("TOKEN")
    respx.post(f"{PT_BASE}/pins").mock(return_value=httpx.Response(200, json={"id": "p1"}))
    result = svc.post_pins("board_123", ["https://pub.r2.dev/img.jpg"], "Title", "Desc")
    assert result == {"ok": True, "pin_ids": ["p1"]}


@respx.mock
def test_pinterest_service_post_pins_fail_fast():
    from app.services.pinterest import PinterestService

    svc = PinterestService("TOKEN")
    respx.post(f"{PT_BASE}/pins").mock(
        side_effect=[
            httpx.Response(200, json={"id": "p1"}),
            httpx.Response(400, json={"message": "Invalid image"}),
        ]
    )
    result = svc.post_pins("board_123", ["url1", "url2", "url3"], "T", "D")
    assert result["ok"] is False
    assert len(respx.calls) == 2


@respx.mock
def test_pinterest_service_create_board_success():
    from app.services.pinterest import PinterestService

    svc = PinterestService("TOKEN")
    respx.post(f"{PT_BASE}/boards").mock(
        return_value=httpx.Response(200, json={"id": "b1", "name": "Fantasy"})
    )
    result = svc.create_board("Fantasy")
    assert result == {"ok": True, "board_id": "b1"}


@respx.mock
def test_pinterest_service_create_board_api_error():
    from app.services.pinterest import PinterestService

    svc = PinterestService("TOKEN")
    respx.post(f"{PT_BASE}/boards").mock(
        return_value=httpx.Response(400, json={"message": "Board name taken"})
    )
    result = svc.create_board("Fantasy")
    assert result["ok"] is False
    assert "Board name taken" in result["description"]


# ── Pinterest router integration tests ───────────────────────────────────────


@respx.mock
def test_post_pinterest_success(client):
    _, pid = _setup(client, "pinterest")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=True)):
        respx.post(f"{PT_BASE}/pins").mock(return_value=httpx.Response(200, json={"id": "pin_001"}))
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@respx.mock
def test_post_pinterest_marks_post_posted(client):
    _, pid = _setup(client, "pinterest")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=True)):
        respx.post(f"{PT_BASE}/pins").mock(return_value=httpx.Response(200, json={"id": "pin_001"}))
        client.post(f"/api/posts/{pid}/post")
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"
    assert post["posted_at"] is not None
    assert post["external_post_id"] == "pin_001"


@respx.mock
def test_post_pinterest_skipped_when_no_token(client):
    _, pid = _setup(client, "pinterest")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=False)):
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "posted"


@respx.mock
def test_post_pinterest_api_error_sets_failed(client):
    _, pid = _setup(client, "pinterest")
    with patch("app.routers.posts.get_or_create_settings", return_value=_mock_settings(pinterest=True)):
        respx.post(f"{PT_BASE}/pins").mock(
            return_value=httpx.Response(400, json={"message": "Invalid board"})
        )
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is False
    post = client.get(f"/api/posts/{pid}").json()
    assert post["status"] == "failed"


@respx.mock
def test_post_pinterest_creates_board_when_not_in_map(client, db):
    """Board name from chosen variant is not in the map → auto-create board, persist, post."""
    from app.models import AIVariant, Series

    sid, pid = _setup(client, "pinterest")
    s = db.get(Series, sid)
    v = AIVariant(
        series_id=sid,
        provider="fake",
        model="fake",
        title="Test",
        title_ru="",
        description_en="Test",
        description_ru="Test",
        tags_instagram="[]",
        tags_telegram="[]",
        pinterest_board="New Art Board",
        pinterest_title="Pin Title",
        pinterest_description="Pin Desc",
    )
    db.add(v)
    db.flush()
    s.chosen_variant_id = v.id
    db.commit()

    settings = _mock_settings(pinterest=True)
    settings.pinterest_board_map = "{}"
    settings.pinterest_default_board_id = None

    respx.post(f"{PT_BASE}/boards").mock(return_value=httpx.Response(200, json={"id": "new_456"}))
    respx.post(f"{PT_BASE}/pins").mock(return_value=httpx.Response(200, json={"id": "pin_001"}))

    with patch("app.routers.posts.get_or_create_settings", return_value=settings):
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True
    board_map = json.loads(settings.pinterest_board_map)
    assert board_map.get("New Art Board") == "new_456"


@respx.mock
def test_post_pinterest_uses_default_when_no_board_name(client):
    """No board name from variant, but default_board_id is set → posts to default."""
    _, pid = _setup(client, "pinterest")
    settings = _mock_settings(pinterest=True)
    settings.pinterest_board_map = "{}"

    respx.post(f"{PT_BASE}/pins").mock(return_value=httpx.Response(200, json={"id": "pin_001"}))

    with patch("app.routers.posts.get_or_create_settings", return_value=settings):
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is True


@respx.mock
def test_post_pinterest_fails_when_no_board_resolved(client):
    """Empty map, no default, no board name → explicit error."""
    _, pid = _setup(client, "pinterest")
    settings = _mock_settings(pinterest=True)
    settings.pinterest_board_map = "{}"
    settings.pinterest_default_board_id = None

    with patch("app.routers.posts.get_or_create_settings", return_value=settings):
        resp = client.post(f"/api/posts/{pid}/post")
    assert resp.json()["success"] is False
    assert "No board resolved" in resp.json()["message"]
