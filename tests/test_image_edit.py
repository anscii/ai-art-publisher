import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import AppConfig
from app.services.ai.catalogue import (
    DEFAULT_IMAGE_EDIT_MODEL,
    IMAGE_EDIT_MODELS,
    IMAGE_EDIT_PRICING,
    calc_image_edit_cost,
    image_edit_provider,
)
from app.services.ai.image_edit import _edit_google, _edit_openai, edit_image


class TestCatalogue:
    def test_every_model_has_price_and_provider(self):
        for m in IMAGE_EDIT_MODELS:
            assert m["id"] in IMAGE_EDIT_PRICING
            assert m["provider"] in {"openai", "google"}

    def test_default_model_listed(self):
        assert image_edit_provider(DEFAULT_IMAGE_EDIT_MODEL) == "openai"

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError):
            image_edit_provider("gpt-image-1")

    def test_cost_formula(self):
        # gpt-image-2.5-flare: 5 / 8 / 30 per MTok
        cost = calc_image_edit_cost("gpt-image-2.5-flare", 100, 1000, 1000)
        assert cost == pytest.approx((100 * 5 + 1000 * 8 + 1000 * 30) / 1_000_000)

    def test_cost_unknown_model_zero(self):
        assert calc_image_edit_cost("nope", 1, 1, 1) == 0.0


class TestOpenAIBackend:
    def test_returns_bytes_and_cost(self):
        resp = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(b"img").decode())],
            usage=SimpleNamespace(
                input_tokens_details=SimpleNamespace(text_tokens=10, image_tokens=500),
                output_tokens=1000,
            ),
        )
        client = MagicMock()
        client.images.edit.return_value = resp
        with patch("openai.OpenAI", return_value=client):
            out, cost = _edit_openai("k", "gpt-image-2", b"src", "image/png", "darker")
        assert out == b"img"
        assert cost == pytest.approx(calc_image_edit_cost("gpt-image-2", 10, 500, 1000))
        assert client.images.edit.call_args.kwargs["model"] == "gpt-image-2"

    def test_no_data_raises(self):
        client = MagicMock()
        client.images.edit.return_value = SimpleNamespace(data=[], usage=None)
        with patch("openai.OpenAI", return_value=client), pytest.raises(ValueError):
            _edit_openai("k", "gpt-image-2", b"src", "image/png", "x")


class TestGoogleBackend:
    def test_returns_bytes_and_cost(self):
        part_text = SimpleNamespace(inline_data=None)
        part_img = SimpleNamespace(inline_data=SimpleNamespace(data=b"img"))
        resp = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part_text, part_img]))],
            usage_metadata=SimpleNamespace(prompt_token_count=300, candidates_token_count=1120),
        )
        client = MagicMock()
        client.models.generate_content.return_value = resp
        with patch("google.genai.Client", return_value=client):
            out, cost = _edit_google("k", "gemini-3.1-flash-image", b"src", "image/jpeg", "darker")
        assert out == b"img"
        assert cost == pytest.approx(calc_image_edit_cost("gemini-3.1-flash-image", 300, 0, 1120))

    def test_no_image_part_raises(self):
        resp = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]))], usage_metadata=None
        )
        client = MagicMock()
        client.models.generate_content.return_value = resp
        with patch("google.genai.Client", return_value=client), pytest.raises(ValueError):
            _edit_google("k", "gemini-3-pro-image", b"src", "image/png", "x")


def test_edit_image_dispatches_by_provider():
    with patch(
        "app.services.ai.image_edit._BACKENDS", {"google": MagicMock(return_value=(b"g", 0.01))}
    ) as b:
        assert edit_image("google", "k", "gemini-3-pro-image", b"s", "image/png", "h") == (
            b"g",
            0.01,
        )
        b["google"].assert_called_once_with("k", "gemini-3-pro-image", b"s", "image/png", "h")


# ── Router integration ────────────────────────────────────────────────────────


def _setup(client):
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/t.jpg", "original_filename": "t.jpg"},
    ).json()["id"]
    storage = MagicMock()
    storage.download_bytes.return_value = b"src"
    storage.public_url.side_effect = lambda k: f"https://pub/{k}"
    return img_id, storage


class TestRouterModelSelection:
    @pytest.fixture(autouse=True)
    def _real_ai(self, monkeypatch):
        monkeypatch.setattr(AppConfig, "fake_ai", False)
        monkeypatch.setattr(AppConfig, "local_storage", False)

    def test_uses_configured_google_model_and_returns_cost(self, client):
        client.put(
            "/api/settings",
            json={"google_api_key": "gk", "image_edit_model": "gemini-3.1-flash-image"},
        )
        img_id, storage = _setup(client)
        with (
            patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage),
            patch("app.services.ai.image_edit.edit_image", return_value=(b"out", 0.0672)) as ed,
        ):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "h"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["model"] == "gemini-3.1-flash-image"
        assert data["cost_usd"] == pytest.approx(0.0672)
        assert ed.call_args.args[:3] == ("google", "gk", "gemini-3.1-flash-image")

    def test_default_model_when_unset(self, client):
        client.put("/api/settings", json={"openai_api_key": "ok"})
        img_id, storage = _setup(client)
        with (
            patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage),
            patch("app.services.ai.image_edit.edit_image", return_value=(b"out", 0.01)) as ed,
        ):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "h"})
        assert resp.status_code == 200
        assert resp.json()["model"] == DEFAULT_IMAGE_EDIT_MODEL
        assert ed.call_args.args[0] == "openai"

    def test_google_model_requires_google_key(self, client):
        client.put(
            "/api/settings",
            json={"openai_api_key": "ok", "image_edit_model": "gemini-3-pro-image"},
        )
        img_id, storage = _setup(client)
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "h"})
        assert resp.status_code == 400
        assert "Google" in resp.json()["detail"]

    def test_unknown_model_400(self, client):
        client.put(
            "/api/settings", json={"openai_api_key": "ok", "image_edit_model": "gpt-image-1"}
        )
        img_id, storage = _setup(client)
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "h"})
        assert resp.status_code == 400


def test_settings_roundtrip_and_providers_list(client):
    client.put("/api/settings", json={"image_edit_model": "gemini-3-pro-image"})
    assert client.get("/api/settings").json()["image_edit_model"] == "gemini-3-pro-image"
    providers = client.get("/api/settings/providers").json()
    assert [m["id"] for m in providers["image_edit"]] == [m["id"] for m in IMAGE_EDIT_MODELS]
