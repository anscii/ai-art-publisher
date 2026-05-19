from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.base import (
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
        "/api/settings",
        json={"anthropic_api_key": "sk-test", "anthropic_default_model": "claude-opus-4-7"},
    )
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 200
    assert all(v["model"] == "claude-opus-4-7" for v in resp.json())


def test_generate_response_includes_cost_usd(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    assert resp.status_code == 200
    assert all("cost_usd" in v for v in resp.json())


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
        client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
        resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 200
    assert len(resp.json()) == 3
    assert resp.json()[0]["title"] == "Dragon Forest"
    assert resp.json()[0]["title_ru"] == "Лес драконов"


def test_generate_appends_not_replaces(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/test.jpg", "original_filename": "test.jpg"},
    )
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    resp = client.post(f"/api/series/{sid}/generate", json={"include_images": True})
    assert resp.status_code == 400


def test_generate_text_only_requires_hint(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    resp = client.post(f"/api/series/{sid}/generate", json={})
    assert resp.status_code == 400
    assert "Hint" in resp.json()["detail"]


def test_generate_text_only_with_hint(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox spirit"})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def _make_series_with_variants(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        client.post(f"/api/series/{sid}/generate", json={"hint": "a fox"})
    variants = client.get(f"/api/series/{sid}").json()["ai_variants"]
    return sid, variants


def test_generate_saves_hint_on_variants(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox spirit"})
    assert resp.status_code == 200
    assert all(v["hint"] == "a fox spirit" for v in resp.json())


def test_generate_hint_none_when_omitted(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    assert all(v["hint"] is None for v in resp.json())


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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    # only 2 images passed, in the requested order (c then a)
    assert len(captured["imgs"]) == 2
    import base64

    assert base64.b64decode(captured["imgs"][0]) == b"img-images/c.jpg"
    assert base64.b64decode(captured["imgs"][1]) == b"img-images/a.jpg"


def test_generate_selected_image_ids_capped_at_3(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "dragons"})
    assert resp.status_code == 200
    v = resp.json()[0]
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        variants = client.post(f"/api/series/{sid}/generate", json={"hint": "test"}).json()
    vid = variants[0]["id"]
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        variants = client.post(f"/api/series/{sid}/generate", json={"hint": "test"}).json()
    vid = variants[0]["id"]
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE)
        mp.return_value = p
        variants = client.post(
            f"/api/series/{sid}/generate", json={"hint": "a ghost in a clockwork city"}
        ).json()
    vid = variants[0]["id"]
    client.put(f"/api/series/{sid}", json={"chosen_variant_id": vid})

    detail = client.get(f"/api/series/{sid}").json()
    assert detail["chosen_variant_id"] == vid
    chosen = next(v for v in detail["ai_variants"] if v["id"] == vid)
    assert chosen["hint"] == "a ghost in a clockwork city"


def test_series_detail_returns_semantic_fields_on_chosen_variant(client):
    """Series detail exposes semantic fields on the chosen variant so the
    frontend can pre-fill the Semantic Layer section on load."""
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_SEMANTIC)
        mp.return_value = p
        variants = client.post(f"/api/series/{sid}/generate", json={"hint": "test"}).json()
    vid = variants[0]["id"]
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


def test_generate_num_variants_passed_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    assert captured["num"] == 2


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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    assert captured["lang"] == "en"


def test_generate_step1_ru_passes_language_to_provider(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    assert captured["lang"] == "ru"


def test_generate_step1_stores_partial_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN)
        mp.return_value = p
        resp = client.post(f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"})
    assert resp.status_code == 200
    variants = resp.json()
    assert len(variants) == 3
    assert all(v["title"] == "" for v in variants)
    assert all(v["description_en"] != "" for v in variants)
    assert all(v["description_ru"] == "" for v in variants)


# ── generate-full endpoint ─────────────────────────────────────────────────────


def test_generate_full_creates_new_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "My description.", "language": "en"},
        )
    assert resp.status_code == 200
    variants = resp.json()["ai_variants"]
    assert len(variants) == 1
    v = variants[0]
    assert v["title"] == "Expanded Title"
    assert v["description_en"] == "My description."
    assert v["description_ru"] != ""


def test_generate_full_updates_existing_variant(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.generate_variants = MagicMock(return_value=_FAKE_PARTIAL_EN)
        mp.return_value = p
        draft_variants = client.post(
            f"/api/series/{sid}/generate", json={"hint": "a fox", "language": "en"}
        ).json()
    vid = draft_variants[0]["id"]

    with patch("app.routers.generate.get_provider") as mp:
        p = MagicMock()
        p.expand_variant = MagicMock(return_value=_FAKE_EXPANDED)
        mp.return_value = p
        resp = client.post(
            f"/api/series/{sid}/generate-full",
            json={"description": "Edited description.", "language": "en", "variant_id": vid},
        )
    assert resp.status_code == 200
    variants = resp.json()["ai_variants"]
    assert len(variants) == 3
    updated = next(v for v in variants if v["id"] == vid)
    assert updated["title"] == "Expanded Title"
    assert updated["description_en"] == "Edited description."


def test_generate_full_missing_series_404(client):
    resp = client.post(
        "/api/series/nonexistent/generate-full",
        json={"description": "text", "language": "en"},
    )
    assert resp.status_code == 404


def test_generate_full_empty_description_400(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    resp = client.post(
        f"/api/series/{sid}/generate-full",
        json={"description": "   ", "language": "en"},
    )
    assert resp.status_code == 400


def test_generate_full_invalid_variant_id_404(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
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
    assert resp.status_code == 200
    assert captured["lang"] == "ru"
    assert captured["desc"] == "My Russian text."
