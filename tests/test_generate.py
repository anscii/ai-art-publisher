from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.base import AIVariantData, fix_llm_tag, fix_llm_text


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
        description_en="Something—wicked.",
        description_ru="Нечто—страшное.",
        tags_instagram=["#dark-fantasy", "#space opera"],
        tags_telegram=["#тёмное фэнтези"],
    )
    assert vd.title == "The End — A Beginning"
    assert vd.description_en == "Something — wicked."
    assert vd.description_ru == "Нечто — страшное."
    assert vd.tags_instagram == ["#dark_fantasy", "#space_opera"]
    assert vd.tags_telegram == ["#тёмное_фэнтези"]


_FAKE = [
    AIVariantData(
        title="Dragon Forest",
        description_en="A mystical forest...",
        description_ru="Мистический лес...",
        tags_instagram=["#art", "#dragon"],
        tags_telegram=["#арт"],
    )
] * 3


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
