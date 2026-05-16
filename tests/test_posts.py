"""Tests for Post CRUD and scheduling via /api/series/{id}/posts and /api/posts/{id}."""


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
    assert resp.status_code == 400


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
        variants = client.post(f"/api/series/{sid}/generate", json={"hint": "test"}).json()

    vid = variants[0]["id"]
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
