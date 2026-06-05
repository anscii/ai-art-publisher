"""Tests for Post CRUD and scheduling via /api/series/{id}/posts and /api/posts/{id}."""

import json as _json
import types

from app.models import Post as _Post
from app.routers.posts import _build_caption, _mark_series_active


def _series_with_image(client, title="Test Series"):
    sid = client.post("/api/series", json={"title": title}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": f"images/{title}.jpg", "original_filename": "test.jpg"},
    ).json()["id"]
    return sid, img_id


def _make_posts(client, sid, img_id, platforms=None):
    if platforms is None:
        platforms = ["telegram", "instagram"]
    return client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": platforms,
            "title": "Forest Dawn",
            "description_telegram": "Лесной рассвет",
            "description_other": "Forest at dawn",
            "tags_telegram": ["#арт"],
            "tags_other": ["#art"],
            "image_ids": [img_id],
        },
    ).json()


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_posts_batch(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram", "instagram"])
    assert len(posts) == 2
    platforms = {p["platform"] for p in posts}
    assert platforms == {"telegram", "instagram"}


def test_create_post_telegram_uses_ru_description(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["description"] == "Лесной рассвет"


def test_create_post_instagram_uses_en_description(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["instagram"])
    assert posts[0]["description"] == "Forest at dawn"


def test_create_post_stores_image_ids(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["image_ids"] == [img_id]


def test_create_post_default_status_draft(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["status"] == "draft"


def test_create_post_invalid_platform(client):
    sid, img_id = _series_with_image(client)
    resp = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["snapchat"],
            "title": "T",
            "description_telegram": "R",
            "description_other": "E",
            "image_ids": [img_id],
        },
    )
    # Pydantic rejects unknown platform values at parse time
    assert resp.status_code == 422


def test_create_post_image_not_in_series(client):
    sid1, _ = _series_with_image(client, "S1")
    sid2, img2 = _series_with_image(client, "S2")
    resp = client.post(
        f"/api/series/{sid1}/posts",
        json={
            "platforms": ["telegram"],
            "title": "T",
            "description_telegram": "R",
            "description_other": "E",
            "image_ids": [img2],
        },
    )
    assert resp.status_code == 400


# ── Read ──────────────────────────────────────────────────────────────────────


def test_list_posts_for_series(client):
    sid, img_id = _series_with_image(client)
    _make_posts(client, sid, img_id, ["telegram", "instagram"])
    data = client.get(f"/api/series/{sid}/posts").json()
    assert len(data) == 2


def test_get_post_detail(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    pid = posts[0]["id"]
    resp = client.get(f"/api/posts/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


def test_posts_appear_in_series_detail(client):
    sid, img_id = _series_with_image(client)
    _make_posts(client, sid, img_id, ["telegram"])
    detail = client.get(f"/api/series/{sid}").json()
    assert len(detail["posts"]) == 1
    assert detail["posts"][0]["platform"] == "telegram"


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_post_title(client):
    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.patch(f"/api/posts/{pid}", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


def test_update_post_description(client):
    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.patch(f"/api/posts/{pid}", json={"description": "Updated"})
    assert resp.json()["description"] == "Updated"


def test_update_post_tags(client):
    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.patch(f"/api/posts/{pid}", json={"tags": ["#new"]})
    assert resp.json()["tags"] == ["#new"]


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_draft_post(client):
    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.delete(f"/api/posts/{pid}")
    assert resp.status_code == 200
    assert client.get(f"/api/posts/{pid}").status_code == 404


def test_delete_posted_post_returns_400(client):
    from unittest.mock import MagicMock, patch

    import httpx
    import respx

    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]

    settings = MagicMock()
    settings.telegram_bot_token = "T"
    settings.telegram_channel_id = "@ch"
    settings.r2_public_base_url = "https://pub.r2.dev"
    settings.facebook_page_id = None

    with respx.mock:
        respx.post("https://api.telegram.org/botT/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with patch("app.routers.posts.get_or_create_settings", return_value=settings):
            client.post(f"/api/posts/{pid}/post")

    resp = client.delete(f"/api/posts/{pid}")
    assert resp.status_code == 400


# ── collection_line ───────────────────────────────────────────────────────────


def test_collection_line_with_number(client):
    cid = client.post("/api/collections", json={"name": "Dark Saga"}).json()["id"]
    sid, img_id = _series_with_image(client)
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    client.put(f"/api/series/{sid}", json={"collection_number": "III"})
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["collection_line"] == "◈ Dark Saga — III"


def test_collection_line_without_number(client):
    cid = client.post("/api/collections", json={"name": "Dark Saga"}).json()["id"]
    sid, img_id = _series_with_image(client)
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    # Clear the auto-assigned number
    client.put(f"/api/series/{sid}", json={"collection_number": ""})
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["collection_line"] == "◈ Dark Saga"


def test_collection_line_no_collection(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["collection_line"] is None


def test_collection_line_editable_on_post(client):
    cid = client.post("/api/collections", json={"name": "Saga"}).json()["id"]
    sid, img_id = _series_with_image(client)
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.patch(f"/api/posts/{pid}", json={"collection_line": "◈ Custom Line"})
    assert resp.json()["collection_line"] == "◈ Custom Line"


# ── title_ru / collection_line_ru ─────────────────────────────────────────────


def test_create_posts_title_ru_stored(client):
    sid, img_id = _series_with_image(client)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "Forest Dawn",
            "title_ru": "Лесной Рассвет",
            "description_telegram": "Описание",
            "description_other": "Description",
            "image_ids": [img_id],
        },
    ).json()
    assert posts[0]["title_ru"] == "Лесной Рассвет"
    # persisted
    detail = client.get(f"/api/posts/{posts[0]['id']}").json()
    assert detail["title_ru"] == "Лесной Рассвет"


def test_create_posts_title_ru_defaults_empty(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["title_ru"] == ""


def test_collection_line_ru_uses_name_ru(client):
    cid = client.post(
        "/api/collections", json={"name": "Dark Saga", "name_ru": "Тёмная Сага"}
    ).json()["id"]
    sid, img_id = _series_with_image(client)
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    client.put(f"/api/series/{sid}", json={"collection_number": "III"})
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["collection_line"] == "◈ Dark Saga — III"
    assert posts[0]["collection_line_ru"] == "◈ Тёмная Сага — III"


def test_collection_line_ru_fallback_to_name_when_no_name_ru(client):
    cid = client.post("/api/collections", json={"name": "Dark Saga"}).json()["id"]
    sid, img_id = _series_with_image(client)
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    client.put(f"/api/series/{sid}", json={"collection_number": ""})
    posts = _make_posts(client, sid, img_id, ["telegram"])
    assert posts[0]["collection_line_ru"] == "◈ Dark Saga"


def test_update_post_ru_fields(client):
    sid, img_id = _series_with_image(client)
    pid = _make_posts(client, sid, img_id, ["telegram"])[0]["id"]
    resp = client.patch(
        f"/api/posts/{pid}",
        json={
            "title_ru": "Новое название",
            "collection_line_ru": "◈ Тёмная Сага #V",
        },
    )
    assert resp.json()["title_ru"] == "Новое название"
    assert resp.json()["collection_line_ru"] == "◈ Тёмная Сага #V"


def test_build_caption_telegram_uses_ru_fields(client):
    """Telegram caption uses title_ru + collection_line_ru when set."""
    from unittest.mock import MagicMock, patch

    import httpx
    import respx

    sid, img_id = _series_with_image(client)
    pid = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "Forest Dawn",
            "title_ru": "Лесной Рассвет",
            "description_telegram": "Описание",
            "description_other": "Description",
            "image_ids": [img_id],
        },
    ).json()[0]["id"]

    settings = MagicMock()
    settings.telegram_bot_token = "T"
    settings.telegram_channel_id = "@ch"
    settings.r2_public_base_url = "https://pub.r2.dev"
    settings.facebook_page_id = None

    captured = {}
    with respx.mock:

        def _capture(request, **kwargs):
            import json as _json

            body = _json.loads(request.content)
            captured["caption"] = body.get("caption") or (body.get("media") or [{}])[0].get(
                "caption", ""
            )
            return httpx.Response(200, json={"ok": True})

        respx.post("https://api.telegram.org/botT/sendMediaGroup").mock(side_effect=_capture)
        with patch("app.routers.posts.get_or_create_settings", return_value=settings):
            client.post(f"/api/posts/{pid}/post")

    assert "Лесной Рассвет" in captured.get("caption", "")
    assert "Forest Dawn" not in captured.get("caption", "")


# ── Semantic metadata / SEO ───────────────────────────────────────────────────


def test_build_caption_instagram_includes_seo():
    """Instagram caption includes Filed under: + seo when seo is set."""
    import json

    from app.models import Post
    from app.routers.posts import _build_caption

    post = Post(
        platform="instagram",
        title="The Forest",
        description="A dark forest.",
        tags=json.dumps(["#art"]),
        seo="dream archaeology • test ruins",
        collection_line=None,
        collection_line_ru=None,
        title_ru=None,
    )
    caption = _build_caption(post)
    assert "Filed under:" in caption
    assert "dream archaeology • test ruins" in caption
    assert "The Forest" in caption
    assert "A dark forest." in caption


def test_build_caption_telegram_excludes_seo():
    """Telegram caption does NOT include Filed under: even when seo is set."""
    import json

    from app.models import Post
    from app.routers.posts import _build_caption

    post = Post(
        platform="telegram",
        title="The Forest",
        title_ru="Лес",
        description="A dark forest.",
        tags=json.dumps(["#арт"]),
        seo="dream archaeology • test ruins",
        collection_line=None,
        collection_line_ru=None,
    )
    caption = _build_caption(post)
    assert "Filed under:" not in caption
    assert "dream archaeology" not in caption


def test_build_caption_telegram_html_formatting():
    """Telegram caption wraps title in <b> and collection line in <i>."""
    import json

    from app.models import Post
    from app.routers.posts import _build_caption

    post = Post(
        platform="telegram",
        title="Forest Dawn",
        title_ru="Лесной Рассвет",
        collection_line="Series One",
        collection_line_ru="Серия Один",
        description="Описание",
        tags=json.dumps(["#арт"]),
    )
    caption = _build_caption(post)
    assert "<b>Лесной Рассвет</b>" in caption
    assert "<i>Серия Один</i>" in caption
    # plain fields unchanged
    assert "Описание" in caption
    assert "#арт" in caption


def test_build_caption_telegram_html_formatting_no_collection():
    """Telegram caption omits <i> tag when collection line is absent."""
    import json

    from app.models import Post
    from app.routers.posts import _build_caption

    post = Post(
        platform="telegram",
        title="Forest Dawn",
        title_ru=None,
        collection_line=None,
        collection_line_ru=None,
        description="Desc",
        tags=json.dumps([]),
    )
    caption = _build_caption(post)
    assert "<b>Forest Dawn</b>" in caption
    assert "<i>" not in caption


def test_create_posts_copies_seo_from_chosen_variant(client):
    """Instagram post gets seo from chosen variant; Telegram post does not."""
    from unittest.mock import MagicMock, patch

    from app.services.ai.base import AIVariantData

    sid, img_id = _series_with_image(client)
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})

    fake_with_seo = [
        AIVariantData(
            title="T",
            title_ru="Т",
            description_en="E",
            description_ru="Р",
            tags_instagram=["#art"],
            tags_telegram=["#арт"],
            instagram_seo="cosmic ruins • dream dust",
        )
    ] * 3

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=fake_with_seo)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "test"})

    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    # set chosen_variant_id
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})

    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram", "instagram"],
            "title": "T",
            "description_telegram": "Р",
            "description_other": "E",
            "image_ids": [img_id],
        },
    ).json()

    ig_post = next(p for p in posts if p["platform"] == "instagram")
    tg_post = next(p for p in posts if p["platform"] == "telegram")

    assert ig_post["seo"] == "cosmic ruins • dream dust"
    assert tg_post["seo"] is None


# ── Auto-mark image / series as posted ───────────────────────────────────────


def _create_platform_post(client, sid, img_ids, platform):
    return client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": [platform],
            "title": "T",
            "description_telegram": "Desc",
            "description_other": "Desc",
            "image_ids": img_ids,
        },
    ).json()[0]["id"]


def _fake_execute(client, pid, settings):
    from unittest.mock import MagicMock, patch

    cfg = MagicMock()
    cfg.fake_posting = True
    with patch("app.routers.posts.get_or_create_settings", return_value=settings):
        with patch("app.routers.posts.get_config", return_value=cfg):
            return client.post(f"/api/posts/{pid}/post")


def test_auto_mark_image_posted_when_both_platforms(client):
    import respx

    from tests.test_posting import _mock_settings

    sid, img_id = _series_with_image(client)
    settings = _mock_settings()

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img_id], "telegram")
        _fake_execute(client, tg_pid, settings)
        # Only telegram done — image must not be marked posted yet
        detail = client.get(f"/api/series/{sid}").json()
        img = next(i for i in detail["images"] if i["id"] == img_id)
        assert img["status"] != "posted"

        ig_pid = _create_platform_post(client, sid, [img_id], "instagram")
        _fake_execute(client, ig_pid, settings)
        # Both platforms done — image must be marked posted
        detail = client.get(f"/api/series/{sid}").json()
        img = next(i for i in detail["images"] if i["id"] == img_id)
        assert img["status"] == "posted"


def test_auto_mark_image_not_posted_if_only_telegram(client):
    import respx

    from tests.test_posting import _mock_settings

    sid, img_id = _series_with_image(client)
    settings = _mock_settings()

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img_id], "telegram")
        _fake_execute(client, tg_pid, settings)

    detail = client.get(f"/api/series/{sid}").json()
    img = next(i for i in detail["images"] if i["id"] == img_id)
    assert img["status"] != "posted"


def test_auto_mark_series_posted_when_all_images_done(client):
    import respx

    from tests.test_posting import _mock_settings

    sid, img_id = _series_with_image(client)
    settings = _mock_settings()

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img_id], "telegram")
        ig_pid = _create_platform_post(client, sid, [img_id], "instagram")
        _fake_execute(client, tg_pid, settings)
        _fake_execute(client, ig_pid, settings)

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "posted"


def test_auto_mark_series_skips_skip_images(client):
    import respx

    from tests.test_posting import _mock_settings

    sid = client.post("/api/series", json={"title": "Multi"}).json()["id"]
    img1 = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/a.jpg", "original_filename": "a.jpg"},
    ).json()["id"]
    img2 = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/b.jpg", "original_filename": "b.jpg"},
    ).json()["id"]
    client.patch(f"/api/images/{img2}/status", json={"status": "skip"})

    settings = _mock_settings()

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img1], "telegram")
        ig_pid = _create_platform_post(client, sid, [img1], "instagram")
        _fake_execute(client, tg_pid, settings)
        _fake_execute(client, ig_pid, settings)

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "posted"


def test_auto_mark_image_posted_telegram_plus_pinterest(client):
    import respx

    from tests.test_posting import _mock_settings

    sid, img_id = _series_with_image(client)
    settings = _mock_settings(pinterest=True)

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img_id], "telegram")
        pt_pid = _create_platform_post(client, sid, [img_id], "pinterest")
        _fake_execute(client, tg_pid, settings)
        detail = client.get(f"/api/series/{sid}").json()
        img = next(i for i in detail["images"] if i["id"] == img_id)
        assert img["status"] != "posted"

        _fake_execute(client, pt_pid, settings)
        detail = client.get(f"/api/series/{sid}").json()
        img = next(i for i in detail["images"] if i["id"] == img_id)
        assert img["status"] == "posted"


# ── _mark_series_active ───────────────────────────────────────────────────────


def test_mark_series_active_sets_active():
    s = types.SimpleNamespace(status="pending")
    _mark_series_active(s)
    assert s.status == "active"


def test_mark_series_active_preserves_skip():
    s = types.SimpleNamespace(status="skip")
    _mark_series_active(s)
    assert s.status == "skip"


def test_mark_series_active_preserves_posted():
    s = types.SimpleNamespace(status="posted")
    _mark_series_active(s)
    assert s.status == "posted"


def test_series_becomes_active_after_single_platform_post(client):
    import respx

    from tests.test_posting import _mock_settings

    sid, img_id = _series_with_image(client)
    settings = _mock_settings()

    with respx.mock:
        tg_pid = _create_platform_post(client, sid, [img_id], "telegram")
        _fake_execute(client, tg_pid, settings)

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["status"] == "active"


def test_create_pinterest_post_valid_platform(client):
    sid, img_id = _series_with_image(client)
    posts = _make_posts(client, sid, img_id, ["pinterest"])
    assert len(posts) == 1
    assert posts[0]["platform"] == "pinterest"


# ── _build_caption ────────────────────────────────────────────────────────────


def _make_post(**kwargs) -> _Post:
    defaults = dict(
        id="test-id",
        series_id="s-id",
        platform="telegram",
        title="Title EN",
        title_ru=None,
        description="Body text",
        tags=_json.dumps([]),
        collection_line=None,
        collection_line_ru=None,
        seo=None,
        status="draft",
        external_post_id=None,
        error_message=None,
        posted_at=None,
        scheduled_at=None,
        deleted_at=None,
    )
    defaults.update(kwargs)
    p = _Post.__new__(_Post)
    p.__dict__.update(defaults)
    return p


def test_build_caption_telegram_joins_parts():
    p = _make_post(
        platform="telegram",
        title="EN Title",
        description="Body",
        tags=_json.dumps(["#tag"]),
    )
    assert _build_caption(p) == "<b>EN Title</b>\n\nBody\n\n#tag"


def test_build_caption_telegram_prefers_ru_title():
    p = _make_post(
        platform="telegram", title="EN", title_ru="RU", description="Body", tags=_json.dumps([])
    )
    assert _build_caption(p).startswith("<b>RU")


def test_build_caption_telegram_falls_back_to_en_title_when_no_ru():
    p = _make_post(
        platform="telegram", title="EN", title_ru=None, description="Body", tags=_json.dumps([])
    )
    assert _build_caption(p).startswith("<b>EN")


def test_build_caption_telegram_prefers_ru_collection_line():
    p = _make_post(
        platform="telegram",
        title="T",
        description="D",
        tags=_json.dumps([]),
        collection_line="EN coll",
        collection_line_ru="RU coll",
    )
    assert "RU coll" in _build_caption(p)
    assert "EN coll" not in _build_caption(p)


def test_build_caption_instagram_uses_en_title():
    p = _make_post(
        platform="instagram", title="EN", title_ru="RU", description="Body", tags=_json.dumps([])
    )
    assert _build_caption(p).startswith("EN")


def test_build_caption_instagram_includes_seo_footer():
    p = _make_post(
        platform="instagram",
        title="T",
        description="D",
        tags=_json.dumps([]),
        seo="keywords here",
    )
    caption = _build_caption(p)
    assert "—\nFiled under:\nkeywords here" in caption


def test_build_caption_telegram_omits_seo_footer():
    p = _make_post(platform="telegram", title="T", description="D", tags=_json.dumps([]), seo="kw")
    assert "Filed under" not in _build_caption(p)


def test_build_caption_skips_empty_parts():
    p = _make_post(platform="instagram", title="T", description="D", tags=_json.dumps([]))
    caption = _build_caption(p)
    assert "\n\n\n" not in caption


def test_build_caption_tags_joined_by_space():
    p = _make_post(
        platform="telegram", title="T", description="D", tags=_json.dumps(["#a", "#b", "#c"])
    )
    assert _build_caption(p).endswith("#a #b #c")


# ── post_to_resp title display ────────────────────────────────────────────────


def test_post_to_resp_telegram_uses_title_ru(client):
    sid, img_id = _series_with_image(client)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "Forest Dawn",
            "title_ru": "Лесной рассвет",
            "description_telegram": "desc",
            "description_other": "desc",
            "tags_telegram": [],
            "tags_other": [],
            "image_ids": [img_id],
        },
    ).json()
    assert posts[0]["title"] == "Лесной рассвет"


def test_post_to_resp_telegram_falls_back_to_en_title_when_no_ru(client):
    sid, img_id = _series_with_image(client)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "Forest Dawn",
            "description_telegram": "desc",
            "description_other": "desc",
            "tags_telegram": [],
            "tags_other": [],
            "image_ids": [img_id],
        },
    ).json()
    assert posts[0]["title"] == "Forest Dawn"


def test_post_to_resp_instagram_always_uses_en_title(client):
    sid, img_id = _series_with_image(client)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["instagram"],
            "title": "Forest Dawn",
            "title_ru": "Лесной рассвет",
            "description_telegram": "desc",
            "description_other": "desc",
            "tags_telegram": [],
            "tags_other": [],
            "image_ids": [img_id],
        },
    ).json()
    assert posts[0]["title"] == "Forest Dawn"
