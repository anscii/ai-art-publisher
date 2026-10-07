from unittest.mock import MagicMock, patch

import pytest

from app.models import AIVariant
from app.services.ai.base import (
    DEFAULT_STYLE_GUIDE,
    AIVariantData,
    _ensure_newlines,
    build_step1_system_prompt,
    build_step2_system_prompt,
    extract_json,
    fix_llm_tag,
    fix_llm_text,
)


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("New Ishtar's infrastructure—a geometry", "New Ishtar's infrastructure — a geometry"),
        ("no dashes here", "no dashes here"),
        ("a—b—c", "a — b — c"),
        ("word— trailing", "word — trailing"),  # letter only on left
        ("leading —word", "leading — word"),  # letter only on right (already has space on left)
        ("—alone—", "— alone —"),  # letters glued on both inner sides
    ],
)
def test_fix_llm_text(inp, expected):
    assert fix_llm_text(inp) == expected


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("#dark-fantasy", "#dark_fantasy"),
        ("#space opera", "#space_opera"),
        ("#already_fine", "#already_fine"),
        ("#multi word-tag", "#multi_word_tag"),
    ],
)
def test_fix_llm_tag(inp, expected):
    assert fix_llm_tag(inp) == expected


def test_ai_variant_data_normalises_on_construction():
    vd = AIVariantData(
        title="The End—A Beginning",
        title_ru="Конец—Начало",
        description_en="Something—wicked.",
        description_ru="Нечто—страшное.",
        tags_instagram=["#dark-fantasy", "#space opera"],
        tags_telegram=["#тёмное фэнтези"],
    )
    assert vd.title == "The End — A Beginning"
    assert vd.title_ru == "Конец — Начало"
    assert vd.description_en == "Something — wicked."
    assert vd.description_ru == "Нечто — страшное."
    assert vd.tags_instagram == ["#dark_fantasy", "#space_opera", "#aiart"]
    assert vd.tags_telegram == ["#тёмное_фэнтези"]


def test_aiart_tag_not_duplicated():
    vd = AIVariantData(
        title="T",
        title_ru="Т",
        description_en="E",
        description_ru="R",
        tags_instagram=["#aiart", "#dark-fantasy"],
        tags_telegram=[],
    )
    assert vd.tags_instagram.count("#aiart") == 1


_FAKE = [
    AIVariantData(
        title="Dragon Forest",
        title_ru="Лес драконов",
        description_en="A mystical forest...",
        description_ru="Мистический лес...",
        tags_instagram=["#art", "#dragon"],
        tags_telegram=["#арт"],
    )
] * 3


def test_generate_uses_provider_default_model(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "default_provider": "anthropic",
            "anthropic_api_key": "sk-test",
            "anthropic_default_model": "claude-opus-4-7",
        },
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    assert resp.json()["generation_status"] == "generating_draft"
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert all(v["model"] == "claude-opus-4-7" for v in variants)


def test_generate_response_includes_cost_usd(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert all("cost_usd" in v for v in variants)


def test_generate_creates_variants(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    with (
        patch("app.routers.generate.get_provider") as mp,
        patch("app.routers.generate.get_storage_from_settings") as ms,
    ):
        ms.return_value = MagicMock(download_bytes=lambda k: b"img")
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        # need an api key set
        client.put(
            "/api/me/settings",
            json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"},
        )
        resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 3
    assert variants[0]["title"] == "Dragon Forest"
    assert variants[0]["title_ru"] == "Лес драконов"


def test_generate_appends_not_replaces(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    for _ in range(2):
        with (
            patch("app.routers.generate.get_provider") as mp,
            patch("app.routers.generate.get_storage_from_settings") as ms,
        ):
            ms.return_value = MagicMock(download_bytes=lambda k: b"img")
            p = MagicMock()
            p.generate_variants = MagicMock(return_value=_FAKE)
            mp.return_value = p
            client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    detail = client.get(f"/api/series/{sid}").json()
    assert len(detail["ai_variants"]) == 6


def test_generate_no_images_returns_400(client):
    sid = client.post("/api/series", json={"title": "Empty"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 400


def test_generate_text_only_requires_hint(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    resp = client.post(f"/api/series/{sid}/generate", json={})
    assert resp.status_code == 400
    assert "Hint" in resp.json()["detail"]


def test_generate_text_only_with_hint(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox spirit"})
    assert resp.status_code == 202
    assert len(client.get(f"/api/series/{sid}").json()["ai_variants"]) == 3


def _make_series_with_variants(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    return sid, variants


def test_generate_saves_hint_on_variants(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox spirit"})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert all(v["hint"] == "a fox spirit" for v in variants)


def test_generate_hint_none_when_omitted(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    with (
        patch("app.routers.generate.get_provider") as mp,
        patch("app.routers.generate.get_storage_from_settings") as ms,
    ):
        ms.return_value = MagicMock(download_bytes=lambda k: b"img")
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert all(v["hint"] is None for v in variants)


def test_hint_preserved_in_series_detail(client):
    sid, variants = _make_series_with_variants(client)
    detail = client.get(f"/api/series/{sid}").json()
    assert all(v["hint"] == "a fox" for v in detail["ai_variants"])


def test_delete_variant(client):
    sid, variants = _make_series_with_variants(client)
    assert len(variants) == 3
    vid = variants[0]["id"]
    resp = client.delete(f"/api/ai_variants/{vid}")
    assert resp.status_code == 200
    remaining = resp.json()["ai_variants"]
    assert len(remaining) == 2
    assert all(v["id"] != vid for v in remaining)


def test_delete_variant_not_found(client):
    resp = client.delete("/api/ai_variants/nonexistent-id")
    assert resp.status_code == 404


# ── Draft with dependent full variants ────────────────────────────────────────


def _make_draft_and_full(client):
    """Create a draft variant (step-1) and a dependent full variant (step-2, different provider)."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "default_provider": "anthropic",
            "anthropic_api_key": "sk-test",
            "openai_api_key": "sk-oa",
        },
    )
    # Step-1 draft (anthropic)
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN[:1])
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "fox"})
    draft_id = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    # Step-2 full (openai, different → new record with draft_id set)
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        client.post(
            f"/api/series/{sid}/generate-full",
            json={
                "description": "Edited.",
                "language": "en",
                "variant_id": draft_id,
                "provider": "openai",
            },
        )
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    full_id = next(v["id"] for v in variants if v["id"] != draft_id)
    return sid, draft_id, full_id


def test_delete_draft_with_dependents_returns_409(client):
    """Deleting a draft that has dependent full variants → 409 with cascade info."""
    _, draft_id, _ = _make_draft_and_full(client)
    resp = client.delete(f"/api/ai_variants/{draft_id}")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["cascade_required"] is True
    assert detail["dependent_count"] == 1


def test_delete_draft_with_dependents_cascade_deletes_both(client):
    """DELETE ?cascade=true removes draft and all dependent full variants."""
    sid, draft_id, full_id = _make_draft_and_full(client)
    resp = client.delete(f"/api/ai_variants/{draft_id}?cascade=true")
    assert resp.status_code == 200
    remaining_ids = [v["id"] for v in resp.json()["ai_variants"]]
    assert draft_id not in remaining_ids
    assert full_id not in remaining_ids


def test_delete_draft_dependent_used_in_post_blocks_cascade(client):
    """Cascade blocked when a dependent full variant is used in a post."""
    sid, draft_id, full_id = _make_draft_and_full(client)
    # Use the full variant in a post
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": full_id})
    _make_post(client, sid)
    resp = client.delete(f"/api/ai_variants/{draft_id}?cascade=true")
    assert resp.status_code == 409
    assert "dependent" in resp.json()["detail"].lower()


def test_delete_full_variant_with_draft_id_no_cascade_needed(client):
    """Deleting a full variant (has draft_id, but is not itself a draft of anything) works directly."""
    _, draft_id, full_id = _make_draft_and_full(client)
    resp = client.delete(f"/api/ai_variants/{full_id}")
    assert resp.status_code == 200
    remaining_ids = [v["id"] for v in resp.json()["ai_variants"]]
    assert full_id not in remaining_ids
    assert draft_id in remaining_ids  # draft untouched


def _make_post(client, sid):
    return client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "T",
            "description_telegram": "d",
            "description_other": "d",
            "image_ids": [],
        },
    )


def test_delete_variant_used_in_posts_blocked(client):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})
    _make_post(client, sid)
    resp = client.delete(f"/api/ai_variants/{vid}")
    assert resp.status_code == 409


def test_delete_chosen_variant_no_posts_allowed(client):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})
    resp = client.delete(f"/api/ai_variants/{vid}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["chosen_variant_id"] is None
    assert all(v["id"] != vid for v in detail["ai_variants"])


def test_delete_unchosen_variant_with_posts_allowed(client):
    sid, variants = _make_series_with_variants(client)
    vid_chosen = variants[0]["id"]
    vid_other = variants[1]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid_chosen})
    _make_post(client, sid)
    resp = client.delete(f"/api/ai_variants/{vid_other}")
    assert resp.status_code == 200
    remaining_ids = [v["id"] for v in resp.json()["ai_variants"]]
    assert vid_other not in remaining_ids
    assert vid_chosen in remaining_ids


def test_used_in_posts_flag_on_variant_response(client):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})
    _make_post(client, sid)
    detail = client.get(f"/api/series/{sid}").json()
    used_map = {v["id"]: v["used_in_posts"] for v in detail["ai_variants"]}
    assert used_map[vid] is True
    assert all(not flag for v_id, flag in used_map.items() if v_id != vid)


def test_delete_variant_preserves_db_row(client, db):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    resp = client.delete(f"/api/ai_variants/{vid}")
    assert resp.status_code == 200
    row = db.get(AIVariant, vid)
    assert row is not None
    assert row.deleted_at is not None


def test_delete_already_deleted_variant_returns_404(client):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    client.delete(f"/api/ai_variants/{vid}")
    resp = client.delete(f"/api/ai_variants/{vid}")
    assert resp.status_code == 404


def test_deleted_variant_absent_from_series_detail(client):
    sid, variants = _make_series_with_variants(client)
    vid = variants[0]["id"]
    client.delete(f"/api/ai_variants/{vid}")
    detail = client.get(f"/api/series/{sid}").json()
    assert all(v["id"] != vid for v in detail["ai_variants"])


def _register_images(client, sid, keys):
    ids = []
    for key in keys:
        r = client.post(
            f"/api/series/{sid}/images/register",
            json={"r2_key": key, "original_filename": key.split("/")[-1]},
        )
        ids.append(r.json()["id"])
    return ids


def test_generate_selected_image_ids_used_in_order(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    img_ids = _register_images(client, sid, ["images/a.jpg", "images/b.jpg", "images/c.jpg"])

    captured = {}
    with (
        patch("app.routers.generate.get_provider") as mp,
        patch("app.routers.generate.get_storage_from_settings") as ms,
    ):
        ms.return_value = MagicMock(download_bytes=lambda k: b"img-" + k.encode())
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda imgs, *a, **kw: (captured.update({"imgs": imgs}) or _FAKE)
        )
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate",
            json={"include_images": True, "selected_image_ids": [img_ids[2], img_ids[0]]},
        )
    assert resp.status_code == 202
    # only 2 images passed, in the requested order (c then a)
    assert len(captured["imgs"]) == 2
    import base64

    assert base64.b64decode(captured["imgs"][0]) == b"img-images/c.jpg"
    assert base64.b64decode(captured["imgs"][1]) == b"img-images/a.jpg"


def test_generate_selected_image_ids_capped_at_3(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    img_ids = _register_images(client, sid, [f"images/{c}.jpg" for c in "abcd"])

    captured = {}
    with (
        patch("app.routers.generate.get_provider") as mp,
        patch("app.routers.generate.get_storage_from_settings") as ms,
    ):
        ms.return_value = MagicMock(download_bytes=lambda k: b"img")
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda imgs, *a, **kw: (captured.update({"imgs": imgs}) or _FAKE)
        )
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate",
            json={"include_images": True, "selected_image_ids": img_ids},
        )
    assert resp.status_code == 202
    assert len(captured["imgs"]) == 3


def test_extract_json_repairs_missing_hashtag_quotes():
    import json

    broken = '[{"tags": ["#Good", #Bad", #AlsoBad"]}]'
    data = json.loads(extract_json(broken))
    assert data[0]["tags"] == ["#Good", "#Bad", "#AlsoBad"]


def test_extract_json_repairs_first_item_missing_quote():
    import json

    broken = '[{"tags": [#OnlyOne"]}]'
    assert json.loads(extract_json(broken))[0]["tags"] == ["#OnlyOne"]


def test_extract_json_leaves_valid_json_unchanged():
    valid = '[{"tags": ["#Good", "#AlsoGood"]}]'
    assert extract_json(valid) == valid


def test_extract_json_repairs_cyrillic_hashtags():
    import json

    broken = '["#Венера", #Биогород"]'
    assert json.loads(extract_json(broken)) == ["#Венера", "#Биогород"]


def test_generate_fallback_to_order_index_without_selected_ids(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    _register_images(client, sid, ["images/x.jpg", "images/y.jpg"])

    captured = {}
    with (
        patch("app.routers.generate.get_provider") as mp,
        patch("app.routers.generate.get_storage_from_settings") as ms,
    ):
        ms.return_value = MagicMock(download_bytes=lambda k: b"img")
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda imgs, *a, **kw: (captured.update({"imgs": imgs}) or _FAKE)
        )
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 202
    assert len(captured["imgs"]) == 2


# ── Semantic metadata ─────────────────────────────────────────────────────────

_FAKE_SEMANTIC = [
    AIVariantData(
        title="Dragon Forest",
        title_ru="Лес драконов",
        description_en="A mystical forest...",
        description_ru="Мистический лес...",
        tags_instagram=["#art", "#dragon"],
        tags_telegram=["#арт"],
        instagram_seo="dream archaeology • test ruins",
        pinterest_title="Fantasy Dragon Forest Art",
        pinterest_description="Dreamlike fantasy art.",
        pinterest_board="Dark Fantasy Art",
        archive_metadata={
            "world_keywords": ["dragons", "forests"],
            "visual_keywords": ["dark", "mystical"],
            "mood_keywords": ["melancholy"],
        },
    )
] * 3


def test_generate_response_includes_semantic_fields(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "dragons"})
    assert resp.status_code == 202
    v = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    assert v["instagram_seo"] == "dream archaeology • test ruins"
    assert v["pinterest_title"] == "Fantasy Dragon Forest Art"
    assert v["pinterest_board"] == "Dark Fantasy Art"
    assert v["archive_metadata"] == {
        "world_keywords": ["dragons", "forests"],
        "visual_keywords": ["dark", "mystical"],
        "mood_keywords": ["melancholy"],
    }


def test_patch_variant_semantic_fields(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "test"})
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    resp = client.patch(
        f"/api/ai_variants/{vid}",
        json={
            "instagram_seo": "updated seo • value",
            "pinterest_title": "Updated Pinterest Title",
            "pinterest_board": "Updated Board",
        },
    )
    assert resp.status_code == 200
    # response is the full SeriesDetail
    updated_variant = next(v for v in resp.json()["ai_variants"] if v["id"] == vid)
    assert updated_variant["instagram_seo"] == "updated seo • value"
    assert updated_variant["pinterest_title"] == "Updated Pinterest Title"
    assert updated_variant["pinterest_board"] == "Updated Board"


def test_patch_variant_partial_update_preserves_other_fields(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "test"})
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    # patch only instagram_seo — other fields should remain
    client.patch(f"/api/ai_variants/{vid}", json={"instagram_seo": "only this changed"})
    resp = client.get(f"/api/series/{sid}")
    updated_variant = next(v for v in resp.json()["ai_variants"] if v["id"] == vid)
    assert updated_variant["instagram_seo"] == "only this changed"
    assert updated_variant["pinterest_title"] == "Fantasy Dragon Forest Art"


def test_patch_variant_not_found(client):
    resp = client.patch("/api/ai_variants/nonexistent", json={"instagram_seo": "x"})
    assert resp.status_code == 404


def test_series_detail_chosen_variant_includes_hint(client):
    """Chosen variant hint must be in series detail so the frontend can
    pre-fill the generate hint field on load without requiring a re-click."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a ghost in a clockwork city"})
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["chosen_variant_id"] == vid
    chosen = next(v for v in detail["ai_variants"] if v["id"] == vid)
    assert chosen["hint"] == "a ghost in a clockwork city"


def test_series_detail_returns_semantic_fields_on_chosen_variant(client):
    """Series detail exposes semantic fields on the chosen variant so the
    frontend can pre-fill the Semantic Layer section on load."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "test"})
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["chosen_variant_id"] == vid

    chosen = next(v for v in detail["ai_variants"] if v["id"] == vid)
    assert chosen["instagram_seo"] == "dream archaeology • test ruins"
    assert chosen["pinterest_title"] == "Fantasy Dragon Forest Art"
    assert chosen["pinterest_board"] == "Dark Fantasy Art"
    assert chosen["archive_metadata"] == {
        "world_keywords": ["dragons", "forests"],
        "visual_keywords": ["dark", "mystical"],
        "mood_keywords": ["melancholy"],
    }


# ── Newline normalisation ─────────────────────────────────────────────────────


def test_ensure_newlines_passthrough_when_already_has_newline():
    text = "First sentence.\nSecond sentence."
    assert _ensure_newlines(text) == text


def test_ensure_newlines_inserts_between_sentences():
    text = "First sentence. Second sentence. Third sentence."
    result = _ensure_newlines(text)
    assert result == "First sentence.\n\nSecond sentence.\n\nThird sentence."


def test_ensure_newlines_single_sentence_unchanged():
    text = "Only one sentence here."
    assert _ensure_newlines(text) == text


def test_ai_variant_data_force_inserts_newlines_on_flat_description():
    vd = AIVariantData(
        title="T",
        title_ru="Т",
        description_en="First sentence. Second sentence.",
        description_ru="Первое предложение. Второе предложение.",
        tags_instagram=[],
        tags_telegram=[],
    )
    assert "\n" in vd.description_en
    assert "\n" in vd.description_ru


def test_build_step1_system_prompt_num_variants():
    prompt = build_step1_system_prompt(1, "en")
    assert "Generate 1 variants" in prompt
    assert "array of 1 objects" in prompt
    assert "description_en" in prompt
    assert "description_ru" not in prompt

    prompt3 = build_step1_system_prompt(3, "ru")
    assert "Generate 3 variants" in prompt3
    assert "array of 3 objects" in prompt3
    assert "description_ru" in prompt3
    assert "description_en" not in prompt3


def test_build_step2_system_prompt_language_en():
    prompt = build_step2_system_prompt("en")
    assert "description_ru" in prompt
    assert "title" in prompt
    assert "JSON object" in prompt


def test_build_step2_system_prompt_language_ru():
    prompt = build_step2_system_prompt("ru")
    assert "description_en" in prompt


def test_prompts_start_with_default_or_custom_style_guide():
    for build in (build_step1_system_prompt, build_step2_system_prompt):
        assert build().startswith(DEFAULT_STYLE_GUIDE)
        assert build(style_guide="  MY STYLE  ").startswith("MY STYLE")
        assert DEFAULT_STYLE_GUIDE not in build(style_guide="MY STYLE")


def test_prompts_keep_contract_markers_with_custom_style_guide():
    p1 = build_step1_system_prompt(2, "en", style_guide="X")
    p2 = build_step2_system_prompt("en", style_guide="X")
    assert "description_en" in p1 and "Respond ONLY with valid JSON" in p1
    for marker in ("description_ru", "title_ru", "archive_classification"):
        assert marker in p2
    assert "Respond ONLY with a valid JSON object" in p2


def test_no_owner_taste_in_app_sources():
    from pathlib import Path

    names = [
        "Zelazny", "Bradbury", "Reynolds", "Lovecraft", "Gaiman",
        "Pratchett", "Bulgakov", "Strugatsky", "Dyachenko",
    ]  # fmt: skip
    for f in Path("app").rglob("*.py"):
        text = f.read_text()
        for n in names:
            assert n not in text, f"{n} in {f}"


def test_openai_provider_sends_style_guide_as_system_prefix():
    from app.services.ai.openai import OpenAIProvider

    with patch("openai.OpenAI"):
        p = OpenAIProvider(api_key="sk-test")
    p.style_guide = "X-STYLE"
    resp = MagicMock()
    resp.choices[
        0
    ].message.content = (
        '{"title": "t", "title_ru": "т", "description_en": "a", "description_ru": "б"}'
    )
    resp.usage.prompt_tokens = resp.usage.completion_tokens = 1
    p._call_api = MagicMock(return_value=resp)
    p.expand_variant("desc", "en", "gpt-4o")
    messages = p._call_api.call_args.args[1]
    assert messages[0]["content"].startswith("X-STYLE")


def _generate_with_style(client, db, email, sub, style):
    from tests.conftest import login_as

    login_as(client, db, email=email, google_sub=sub)
    client.put(
        "/api/me/settings",
        json={"default_provider": "anthropic", "anthropic_api_key": "sk", "style_guide": style},
    )
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    return p.style_guide


def test_generate_applies_only_own_style_guide(client, db):
    assert _generate_with_style(client, db, "a@x.com", "ga", "MY STYLE") == "MY STYLE"
    assert _generate_with_style(client, db, "b@x.com", "gb", "") == ""


def test_generate_num_variants_passed_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    captured = {}
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update({"num": kw.get("num_variants")}) or _FAKE[:2]
            )
        )
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "num_variants": 2})
    assert resp.status_code == 202
    assert captured["num"] == 2


def test_generate_returns_newest_variants_first(client):
    """series_to_detail sorts by generated_at desc — new drafts must be at index 0."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    # First batch: 1 full variant
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE[:1])
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "old", "num_variants": 1})
    # Second batch: 2 new partial drafts
    _two_drafts = [
        AIVariantData(
            title="",
            title_ru="",
            description_en=f"Draft {i}.\n\nSecond.",
            description_ru="",
            tags_instagram=[],
            tags_telegram=[],
        )
        for i in range(2)
    ]
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_two_drafts)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "new", "num_variants": 2})
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 3
    # Newest-first: new partial drafts at index 0 and 1
    assert variants[0]["title"] == ""
    assert variants[1]["title"] == ""
    assert variants[2]["title"] == "Dragon Forest"  # the old full variant


def test_generate_partial_variant_has_model_field(client):
    """Partial (step-1) variants must carry the model name for display."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "default_provider": "anthropic",
            "anthropic_api_key": "sk-test",
            "anthropic_default_model": "claude-sonnet-4-6",
        },
    )
    _draft = [
        AIVariantData(
            title="",
            title_ru="",
            description_en="Draft.\n\nTwo.",
            description_ru="",
            tags_instagram=[],
            tags_telegram=[],
        )
    ]
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_draft)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "test"})
    assert resp.status_code == 202
    assert client.get(f"/api/series/{sid}").json()["ai_variants"][0]["model"] == "claude-sonnet-4-6"


# ── Step 1: partial variant generation ────────────────────────────────────────

_FAKE_PARTIAL_EN = [
    AIVariantData(
        title="",
        title_ru="",
        description_en=f"Fake English description {i + 1}.\n\nSecond sentence.",
        description_ru="",
        tags_instagram=[],
        tags_telegram=[],
        cost_usd=0.001,
    )
    for i in range(3)
]

_FAKE_PARTIAL_RU = [
    AIVariantData(
        title="",
        title_ru="",
        description_en="",
        description_ru=f"Фейковое описание {i + 1}.\n\nВторое предложение.",
        tags_instagram=[],
        tags_telegram=[],
        cost_usd=0.001,
    )
    for i in range(3)
]

_FAKE_EXPANDED = AIVariantData(
    title="Expanded Title",
    title_ru="Расширенный заголовок",
    description_en="Expanded English description.\n\nSecond sentence.",
    description_ru="Расширенное русское описание.\n\nВторое предложение.",
    tags_instagram=["#expanded", "#test"],
    tags_telegram=["#расширен"],
    instagram_seo="expanded archaeology • test ruins",
    pinterest_title="Expanded Pinterest Title",
    pinterest_description="Expanded Pinterest description.",
    pinterest_board="Expanded Board",
    archive_metadata={
        "world_keywords": ["expanded", "test"],
        "visual_keywords": ["bright"],
        "mood_keywords": ["hopeful"],
    },
    cost_usd=0.005,
)


def test_generate_step1_passes_language_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    captured = {}
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update({"lang": kw.get("language")}) or _FAKE_PARTIAL_EN
            )
        )
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    assert resp.status_code == 202
    assert captured["lang"] == "en"


def test_generate_step1_ru_passes_language_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    captured = {}
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update({"lang": kw.get("language")}) or _FAKE_PARTIAL_RU
            )
        )
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "ru"})
    assert resp.status_code == 202
    assert captured["lang"] == "ru"


def test_generate_step1_stores_partial_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 3
    assert all(v["title"] == "" for v in variants)
    assert all(v["description_en"] != "" for v in variants)
    assert all(v["description_ru"] == "" for v in variants)


# ── generate-full endpoint ─────────────────────────────────────────────────────


def test_generate_full_creates_new_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My description.", "language": "en"},
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 1
    v = variants[0]
    assert v["title"] == "Expanded Title"
    assert v["description_en"] == "My description."
    assert v["description_ru"] != ""


def test_generate_full_updates_existing_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "Edited description.", "language": "en", "variant_id": vid},
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 3
    updated = next(v for v in variants if v["id"] == vid)
    assert updated["title"] == "Expanded Title"
    assert updated["description_en"] == "Edited description."


def test_generate_full_same_provider_draft_updates_in_place(client):
    """Draft + same provider/model as full gen → update in-place, no new record."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN[:1])
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    draft_variant = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    vid = draft_variant["id"]
    original_provider = draft_variant["provider"]

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={
                "description": "My edited description.",
                "language": "en",
                "variant_id": vid,
                # no provider override — resolves to same defaults as draft
            },
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    # updated in-place: still 1 record
    assert len(variants) == 1
    updated = variants[0]
    assert updated["id"] == vid
    assert updated["title"] == "Expanded Title"
    assert updated["description_en"] == "My edited description."
    assert updated["provider"] == original_provider


def test_generate_full_different_provider_creates_new_variant(client):
    """Draft + different provider for full gen → new variant created, draft preserved."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "default_provider": "anthropic",
            "anthropic_api_key": "sk-test",
            "openai_api_key": "sk-oa",
        },
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN[:1])
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    draft_variant = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    vid = draft_variant["id"]
    assert draft_variant["provider"] == "anthropic"

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={
                "description": "Edited description.",
                "language": "en",
                "variant_id": vid,
                "provider": "openai",
            },
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    # new variant created alongside the draft
    assert len(variants) == 2
    # original draft untouched
    draft = next(v for v in variants if v["id"] == vid)
    assert draft["title"] == ""
    assert draft["provider"] == "anthropic"
    # new full variant carries openai + draft description
    new_v = next(v for v in variants if v["id"] != vid)
    assert new_v["provider"] == "openai"
    assert new_v["title"] == "Expanded Title"
    assert new_v["description_en"] == "Edited description."


def test_generate_full_on_full_variant_creates_new(client):
    """Regenerating full content on an already-full variant creates new record, original untouched."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp1 = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "First full description.", "language": "en"},
        )
    assert resp1.status_code == 202
    full_vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]

    _FAKE_EXPANDED_2 = AIVariantData(
        title="Second Full Title",
        title_ru="Второй заголовок",
        description_en="Second full description.\n\nSentence two.",
        description_ru="Второе полное описание.\n\nПредложение два.",
        tags_instagram=["#second"],
        tags_telegram=["#второй"],
        cost_usd=0.003,
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED_2)
        mp.return_value = p
        resp2 = client.post(
            f"/api/series/{sid}/generate-full",
            json={
                "description": "Second full description.",
                "language": "en",
                "variant_id": full_vid,
            },
        )
    assert resp2.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    # new variant created — 2 total
    assert len(variants) == 2
    original = next(v for v in variants if v["id"] == full_vid)
    assert original["title"] == "Expanded Title"
    new_v = next(v for v in variants if v["id"] != full_vid)
    assert new_v["title"] == "Second Full Title"
    assert new_v["description_en"] == "Second full description."


def test_generate_full_missing_series_404(client):
    resp = client.post(
        "/api/series/nonexistent/generate-full",
        json={"description": "text", "language": "en"},
    )
    assert resp.status_code == 404


def test_generate_full_empty_description_400(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    resp = client.post(
        f"/api/series/{sid}/generate-full",
        json={"description": "   ", "language": "en"},
    )
    assert resp.status_code == 400


def test_generate_full_invalid_variant_id_404(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "text", "language": "en", "variant_id": "nonexistent"},
        )
    assert resp.status_code == 404


def test_generate_full_passes_language_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    captured = {}
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(
            side_effect=lambda desc, lang, *a, **kw: (
                captured.update({"desc": desc, "lang": lang}) or _FAKE_EXPANDED
            )
        )
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My Russian text.", "language": "ru"},
        )
    assert resp.status_code == 202
    assert captured["lang"] == "ru"
    assert captured["desc"] == "My Russian text."


def test_generate_uses_openrouter_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or-key", "default_provider": "openrouter"},
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    mp.assert_called_once_with("openrouter", "sk-or-key")


def test_generate_openrouter_uses_default_model_from_settings(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "openrouter_api_key": "sk-or-key",
            "default_provider": "openrouter",
            "openrouter_default_model": "google/gemma-4-31b-it:free",
        },
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert all(v["model"] == "google/gemma-4-31b-it:free" for v in variants)


def test_generate_openrouter_no_key_returns_400(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 400
    assert "openrouter" in resp.json()["detail"].lower()


def test_generate_error_detail_is_plain_string(client):
    """400 errors from the generate endpoint return detail as a plain string.

    The frontend apiFetch handler must receive a string (not an array) so it can
    surface a readable message.  This test guards against accidentally using a
    response shape that would render as '[object Object]' in the UI.
    """
    sid = client.post("/api/series", json={}).json()["id"]
    resp = client.post(
        f"/api/series/{sid}/generate",
        json={"hint": None, "include_images": False},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, str), f"detail must be str, got {type(detail)}: {detail!r}"
    assert "hint" in detail.lower()


# ── _resolve_actual_provider_model helper ─────────────────────────────────────


def test_resolve_actual_provider_model_uses_actual_model():
    from app.routers.generate import _resolve_actual_provider_model

    assert _resolve_actual_provider_model(
        "google/gemma-3-27b-it:free", "openrouter", "openrouter/free"
    ) == ("openrouter", "google/gemma-3-27b-it:free")


def test_resolve_actual_provider_model_none_returns_requested():
    from app.routers.generate import _resolve_actual_provider_model

    assert _resolve_actual_provider_model(None, "openrouter", "openrouter/free") == (
        "openrouter",
        "openrouter/free",
    )


def test_resolve_actual_provider_model_non_openrouter_passthrough():
    from app.routers.generate import _resolve_actual_provider_model

    assert _resolve_actual_provider_model(None, "anthropic", "claude-sonnet-4-6") == (
        "anthropic",
        "claude-sonnet-4-6",
    )


# ── OpenRouter actual model storage ───────────────────────────────────────────


def _make_actual_variants(actual_model: str | None):
    """Return _FAKE_PARTIAL_EN variants with actual_model set."""
    variants = [
        AIVariantData(
            title="",
            title_ru="",
            description_en=f"Desc {i}.\n\nTwo.",
            description_ru="",
            tags_instagram=[],
            tags_telegram=[],
            actual_model=actual_model,
        )
        for i in range(1)
    ]
    return variants


def test_generate_openrouter_stores_actual_model_and_provider(client):
    """When OpenRouter returns a real model, store actual provider+model in AIVariant."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or", "default_provider": "openrouter"},
    )
    actual_variants = _make_actual_variants("google/gemma-3-27b-it:free")
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=actual_variants)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    v = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    assert v["model"] == "google/gemma-3-27b-it:free"
    assert v["provider"] == "openrouter"


def test_generate_openrouter_no_actual_model_stores_requested(client):
    """When actual_model is None, store the requested provider+model."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or", "default_provider": "openrouter"},
    )
    actual_variants = _make_actual_variants(None)
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=actual_variants)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    v = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    assert v["model"] == "openrouter/free"
    assert v["provider"] == "openrouter"


def test_generate_full_openrouter_stores_actual_provider_and_model(client):
    """generate-full stores actual provider+model when OpenRouter resolves it."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or", "default_provider": "openrouter"},
    )
    expanded = AIVariantData(
        title="Expanded Title",
        title_ru="Расш. заголовок",
        description_en="Expanded.\n\nTwo.",
        description_ru="Расш.\n\nДва.",
        tags_instagram=["#test"],
        tags_telegram=[],
        actual_model="google/gemma-3-27b-it:free",
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=expanded)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My description.", "language": "en"},
        )
    assert resp.status_code == 202
    v = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    assert v["model"] == "google/gemma-3-27b-it:free"
    assert v["provider"] == "openrouter"


def test_generate_full_openrouter_same_actual_model_updates_draft_in_place(client):
    """Draft stored with actual provider/model; same actual model on expand → in-place update."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or", "default_provider": "openrouter"},
    )
    # Step 1: create draft with actual_model set
    draft_variants = _make_actual_variants("google/gemma-3-27b-it:free")
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=draft_variants)
        mp.return_value = p
        draft_resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert draft_resp.status_code == 202
    draft_variant = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    vid = draft_variant["id"]
    assert draft_variant["provider"] == "openrouter"
    assert draft_variant["model"] == "google/gemma-3-27b-it:free"

    # Step 2: expand with same actual model → in-place update
    expanded = AIVariantData(
        title="Expanded Title",
        title_ru="Расш. заголовок",
        description_en="My edited desc.\n\nTwo.",
        description_ru="Расш.\n\nДва.",
        tags_instagram=["#test"],
        tags_telegram=[],
        actual_model="google/gemma-3-27b-it:free",
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=expanded)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My edited desc.", "language": "en", "variant_id": vid},
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 1  # updated in-place
    assert variants[0]["id"] == vid
    assert variants[0]["title"] == "Expanded Title"


def test_generate_full_openrouter_different_actual_model_creates_new_record(client):
    """Different actual model on expand → new record created, draft preserved."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={"openrouter_api_key": "sk-or", "default_provider": "openrouter"},
    )
    # Step 1: draft with google model
    draft_variants = _make_actual_variants("google/gemma-3-27b-it:free")
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=draft_variants)
        mp.return_value = p
        draft_resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert draft_resp.status_code == 202
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]

    # Step 2: expand with different actual model → new record
    expanded = AIVariantData(
        title="New Title",
        title_ru="Новый заголовок",
        description_en="New desc.\n\nTwo.",
        description_ru="Нов.\n\nДва.",
        tags_instagram=["#test"],
        tags_telegram=[],
        actual_model="openai/gpt-oss-120b:free",
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=expanded)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "New desc.", "language": "en", "variant_id": vid},
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    assert len(variants) == 2  # new record alongside draft
    # original draft preserved
    draft = next(v for v in variants if v["id"] == vid)
    assert draft["title"] == ""
    assert draft["provider"] == "openrouter"
    # new variant still openrouter provider, but different actual model
    new_v = next(v for v in variants if v["id"] != vid)
    assert new_v["provider"] == "openrouter"
    assert new_v["model"] == "openai/gpt-oss-120b:free"
    assert new_v["title"] == "New Title"


# ── draft_id provenance tracking ──────────────────────────────────────────────


def test_generate_full_new_record_sets_draft_id(client):
    """New full-gen variant from a draft must carry draft_id pointing to the source."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings",
        json={
            "default_provider": "anthropic",
            "anthropic_api_key": "sk-test",
            "openai_api_key": "sk-oa",
        },
    )
    # Step 1: draft with anthropic
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN[:1])
        mp.return_value = p
        draft_resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert draft_resp.status_code == 202
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]

    # Step 2: full-gen with different provider → new record
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={
                "description": "Edited description.",
                "language": "en",
                "variant_id": vid,
                "provider": "openai",
            },
        )
    assert resp.status_code == 202
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    new_v = next(v for v in variants if v["id"] != vid)
    assert new_v["draft_id"] == vid


def test_generate_full_in_place_draft_id_is_none(client):
    """In-place update (same provider/model) must not set draft_id."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN[:1])
        mp.return_value = p
        draft_resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert draft_resp.status_code == 202
    vid = client.get(f"/api/series/{sid}").json()["ai_variants"][0]["id"]

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My edited description.", "language": "en", "variant_id": vid},
        )
    assert resp.status_code == 202
    updated = next(
        v for v in client.get(f"/api/series/{sid}").json()["ai_variants"] if v["id"] == vid
    )
    assert updated["draft_id"] is None


def test_generate_full_no_variant_id_draft_id_is_none(client):
    """Fresh generate-full without variant_id must have draft_id=None."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My description.", "language": "en"},
        )
    assert resp.status_code == 202
    v = client.get(f"/api/series/{sid}").json()["ai_variants"][0]
    assert v["draft_id"] is None


def test_generate_step1_draft_id_is_none(client):
    """Step-1 variants (generate endpoint) always have draft_id=None."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    assert all(
        v["draft_id"] is None for v in client.get(f"/api/series/{sid}").json()["ai_variants"]
    )


# ── Background generation status ──────────────────────────────────────────────


def test_generate_returns_generating_status_immediately(client):
    """POST /generate responds with generation_status='generating_draft' before BG task runs."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202
    assert resp.json()["generation_status"] == "generating_draft"


def test_generate_409_when_already_generating(client, db):
    """Second POST /generate while first is running returns 409."""
    from app.models import Series as _Series

    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    # Manually set generation_status to simulate an in-progress generation.
    s = db.get(_Series, sid)
    s.generation_status = "generating_draft"
    db.commit()
    resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 409
    assert "in progress" in resp.json()["detail"].lower()


def test_generate_full_409_when_already_generating(client, db):
    from app.models import Series as _Series

    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    s = db.get(_Series, sid)
    s.generation_status = "generating_full"
    db.commit()
    resp = client.post(
        f"/api/series/{sid}/generate-full",
        json={"description": "Some text.", "language": "en"},
    )
    assert resp.status_code == 409


def test_generate_background_sets_idle_on_success(client, db):
    """Background task sets generation_status='idle' after completing."""
    from app.models import Series as _Series
    from app.routers.generate import _run_generate_variants

    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    s = db.get(_Series, sid)
    s.generation_status = "generating_draft"
    db.commit()
    db.expire_all()

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        _run_generate_variants(
            sid,
            {
                "hint": "a fox",
                "num_variants": 1,
                "language": "en",
                "include_images": False,
                "selected_image_ids": None,
                "provider": None,
                "model": None,
            },
            db,
        )

    db.expire_all()
    s = db.get(_Series, sid)
    assert s.generation_status == "idle"
    assert s.generation_error is None
    assert len(s.ai_variants) == 3


def test_generate_full_background_sets_idle_on_success(client, db):
    """generate-full background task sets generation_status='idle' after completing."""
    from app.models import Series as _Series
    from app.routers.generate import _run_generate_full

    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    s = db.get(_Series, sid)
    s.generation_status = "generating_full"
    db.commit()
    db.expire_all()

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        _run_generate_full(
            sid,
            {
                "description": "My text.",
                "language": "en",
                "variant_id": None,
                "hint": None,
                "provider": None,
                "model": None,
            },
            db,
        )

    db.expire_all()
    s = db.get(_Series, sid)
    assert s.generation_status == "idle"
    assert len(s.ai_variants) == 1


# ── per-user keys / non-admin access (2A) ─────────────────────────────────────


def _own_series(db, user, name="mine"):
    from app.models import Series

    s = Series(name=name, user_id=user.id)
    db.add(s)
    db.commit()
    return s.id


def test_non_admin_generates_with_own_key(client, db):
    from tests.conftest import login_as

    u = login_as(client, db)
    sid = _own_series(db, u)
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-mine"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate", json={"hint": "a fox", "provider": "anthropic"}
        )
    assert resp.status_code == 202
    assert mp.call_args.args == ("anthropic", "sk-mine")
    assert client.get(f"/api/series/{sid}").json()["ai_variants"]


def test_non_admin_fake_ai_generates_without_key(client, db, monkeypatch):
    from app.config import AppConfig
    from tests.conftest import login_as

    monkeypatch.setattr(AppConfig, "fake_ai", True)
    u = login_as(client, db)
    sid = _own_series(db, u)
    resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 202


def test_non_admin_without_key_gets_settings_hint(client, db):
    from tests.conftest import login_as

    u = login_as(client, db)
    sid = _own_series(db, u)
    resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "provider": "google"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No Google key. Add one in Settings."
    resp = client.post(
        f"/api/series/{sid}/generate-full", json={"description": "d", "provider": "openai"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No OpenAI key. Add one in Settings."


def test_other_users_key_is_not_used(client, db):
    from tests.conftest import login_as

    login_as(client, db, email="a@x.com", google_sub="ga")
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-a"})
    b = login_as(client, db, email="b@x.com", google_sub="gb")
    sid = _own_series(db, b)
    resp = client.post(
        f"/api/series/{sid}/generate", json={"hint": "a fox", "provider": "anthropic"}
    )
    assert resp.status_code == 400
    assert "Add one in Settings" in resp.json()["detail"]


@pytest.mark.parametrize("is_admin,expected", [(False, False), (True, True)])
def test_board_context_only_for_admin_owned_series(client, db, is_admin, expected):
    import app.routers.generate as gen
    from app.routers.settings import get_or_create_settings
    from tests.conftest import login_as

    u = login_as(client, db, is_admin=is_admin)
    sid = _own_series(db, u)
    get_or_create_settings(db).pinterest_board_map = '{"Dark Fantasy Art": "1"}'
    client.put(
        "/api/me/settings", json={"anthropic_api_key": "sk", "default_provider": "anthropic"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        gen._run_generate_variants(sid, {"hint": "a fox"}, db)
    assert ("Existing Pinterest boards" in p.generate_variants.call_args.args[2]) is expected


# ── Default AI Access + AI Request ledger ─────────────────────────────────────

_FREE_MODEL = "google/gemma-4-31b-it:free"


def _enable_default_ai(db, key="sk-instance", limit=20):
    from app.routers.settings import get_or_create_settings

    s = get_or_create_settings(db)
    s.default_ai_openrouter_key = key
    s.default_ai_daily_limit = limit
    db.commit()


def _ledger(db):
    from app.models import AIRequest

    db.expire_all()
    return db.query(AIRequest).all()


def _keyless_generate(client, sid, **extra):
    return client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", **extra})


def test_keyless_default_access_records_via_default_row(client, db, monkeypatch):
    from app.config import AppConfig

    monkeypatch.setattr(AppConfig, "fake_ai", True)
    _enable_default_ai(db)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    resp = _keyless_generate(client, sid)
    assert resp.status_code == 202
    rows = _ledger(db)
    assert len(rows) == 1
    assert rows[0].via_default_access is True
    assert rows[0].kind == "draft"
    assert rows[0].model == "openrouter/free"


def test_over_quota_returns_429_and_status_unchanged(client, db, monkeypatch):
    from app.config import AppConfig
    from app.models import Series

    monkeypatch.setattr(AppConfig, "fake_ai", True)
    _enable_default_ai(db, limit=2)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    for _ in range(2):
        assert _keyless_generate(client, sid).status_code == 202
        s = db.get(Series, sid)
        s.generation_status = "idle"
        db.commit()
    resp = _keyless_generate(client, sid)
    assert resp.status_code == 429
    assert "Daily free limit reached (2/day)" in resp.json()["detail"]
    db.expire_all()
    assert db.get(Series, sid).generation_status == "idle"
    assert len(_ledger(db)) == 2


def test_own_key_row_not_via_default_and_not_counted(client, db):
    _enable_default_ai(db, limit=1)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        for _ in range(3):
            assert _keyless_generate(client, sid).status_code == 202
    rows = _ledger(db)
    assert len(rows) == 3
    assert all(r.via_default_access is False for r in rows)


def test_generate_full_bad_variant_burns_no_quota(client, db):
    _enable_default_ai(db)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put(
        "/api/me/settings", json={"default_provider": "anthropic", "anthropic_api_key": "sk-test"}
    )
    resp = client.post(
        f"/api/series/{sid}/generate-full",
        json={"description": "text", "variant_id": "nope"},
    )
    assert resp.status_code == 404
    assert _ledger(db) == []


def test_background_uses_instance_key_when_via_default(client, db):
    _enable_default_ai(db, key="sk-instance")
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = _keyless_generate(client, sid, model=_FREE_MODEL)
    assert resp.status_code == 202
    mp.assert_called_once_with("openrouter", "sk-instance")


def test_body_cannot_smuggle_ai_request_id_or_paid_model(client, db):
    _enable_default_ai(db)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    payload = {"ai_request_id": "zzz", "provider": "openrouter"}
    resp = _keyless_generate(client, sid, model="openai/gpt-6", **payload)
    assert resp.status_code == 400
    assert "free models only" in resp.json()["detail"]
    assert _ledger(db) == []

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = _keyless_generate(client, sid, model=_FREE_MODEL, **payload)
    assert resp.status_code == 202
    rows = _ledger(db)
    assert len(rows) == 1
    assert rows[0].id != "zzz"


def test_ledger_cost_is_one_call_not_times_variants(client, db):
    from app.services.ai.base import AIVariantData

    _enable_default_ai(db)
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/me/settings", json={"default_provider": "openrouter"})
    three = [
        AIVariantData(
            title="t",
            title_ru="т",
            description_en="d",
            description_ru="д",
            cost_usd=0.01,
        )
        for _ in range(3)
    ]
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=three)
        mp.return_value = p
        assert _keyless_generate(client, sid, num_variants=3).status_code == 202
    rows = _ledger(db)
    assert len(rows) == 1
    assert rows[0].cost_usd == pytest.approx(0.01)
