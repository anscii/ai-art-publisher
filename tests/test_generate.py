from unittest.mock import MagicMock, patch

from app.services.ai.base import AIVariantData

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
        resp = client.post(f"/api/series/{sid}/generate", json={})
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
            client.post(f"/api/series/{sid}/generate", json={})
    detail = client.get(f"/api/series/{sid}").json()
    assert len(detail["ai_variants"]) == 6


def test_generate_no_images_returns_400(client):
    sid = client.post("/api/series", json={"title": "Empty"}).json()["id"]
    client.put("/api/settings", json={"anthropic_api_key": "sk-test"})
    resp = client.post(f"/api/series/{sid}/generate", json={})
    assert resp.status_code == 400
