"""Tests for GoogleProvider on the google-genai SDK and the _test_google connection check."""

import base64
import io
import json
from unittest.mock import MagicMock, patch

import PIL.Image
from google.genai import types

from app.routers.settings import _test_google
from app.services.ai.base import MAX_OUTPUT_TOKENS, build_step2_user_text
from app.services.ai.google import GoogleProvider

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_provider():
    with patch("app.services.ai.google.genai.Client") as mock_client_cls:
        provider = GoogleProvider(api_key="test-key")
    return provider, mock_client_cls


def _b64_png() -> str:
    img = PIL.Image.new("RGB", (2, 2), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _usage_resp(text: str, prompt_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = MagicMock(
        prompt_token_count=prompt_tokens, candidates_token_count=output_tokens
    )
    return resp


# ── GoogleProvider.__init__ ───────────────────────────────────────────────────


def test_init_creates_client():
    with patch("app.services.ai.google.genai.Client") as mock_client_cls:
        GoogleProvider(api_key="test-key")
    mock_client_cls.assert_called_once_with(api_key="test-key")


# ── generate_variants ──────────────────────────────────────────────────────────


def test_generate_variants_calls_generate_content_with_images_and_config():
    provider, _ = _make_provider()
    raw = [{"description_en": "Desc one.\n\nTwo."}, {"description_en": "Desc two.\n\nTwo."}]
    provider._client.models.generate_content.return_value = _usage_resp(json.dumps(raw))

    variants = provider.generate_variants(
        [_b64_png()], "gemini-2.5-flash", hint="hint text", num_variants=2, language="en"
    )

    assert len(variants) == 2
    assert variants[0].description_en == "Desc one.\n\nTwo."
    assert variants[1].description_en == "Desc two.\n\nTwo."

    _, kwargs = provider._client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.5-flash"

    contents = kwargs["contents"]
    assert len(contents) == 2
    assert isinstance(contents[0], PIL.Image.Image)
    assert isinstance(contents[-1], str)
    assert "hint text" in contents[-1]

    config = kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction is not None
    assert config.temperature == 1.0
    assert config.top_p == 0.95
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS


def test_generate_variants_attaches_usage_and_cost():
    provider, _ = _make_provider()
    raw = [{"description_en": "Desc.\n\nTwo."}]
    provider._client.models.generate_content.return_value = _usage_resp(
        json.dumps(raw), prompt_tokens=123, output_tokens=45
    )

    variants = provider.generate_variants([_b64_png()], "gemini-2.5-flash")

    assert len(variants) == 1
    assert variants[0].input_tokens == 123
    assert variants[0].output_tokens == 45
    assert variants[0].cost_usd > 0


# ── expand_variant ──────────────────────────────────────────────────────────────


def test_expand_variant_calls_generate_content_with_text_contents():
    provider, _ = _make_provider()
    raw = {"title": "T", "title_ru": "Т", "description_ru": "Расш.\n\nДва."}
    provider._client.models.generate_content.return_value = _usage_resp(
        json.dumps(raw), prompt_tokens=10, output_tokens=20
    )

    data = provider.expand_variant("My desc.\n\nTwo.", "en", "gemini-2.5-flash", hint="ctx")

    assert data.description_en == "My desc.\n\nTwo."
    assert data.description_ru == "Расш.\n\nДва."
    assert data.input_tokens == 10
    assert data.output_tokens == 20

    _, kwargs = provider._client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["contents"] == build_step2_user_text("My desc.\n\nTwo.", "en", "ctx")

    config = kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction is not None
    assert config.temperature == 1.0
    assert config.top_p == 0.95
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS


def test_expand_variant_russian_keeps_primary_in_description_ru():
    provider, _ = _make_provider()
    raw = {"title": "T", "title_ru": "Т", "description_en": "Expanded.\n\nTwo."}
    provider._client.models.generate_content.return_value = _usage_resp(json.dumps(raw))

    data = provider.expand_variant("Исходное.\n\nДва.", "ru", "gemini-2.5-flash")

    assert data.description_ru == "Исходное.\n\nДва."
    assert data.description_en == "Expanded.\n\nTwo."


# ── _test_google connection check ─────────────────────────────────────────────


def test_test_google_missing_key():
    assert _test_google("") == {"ok": False, "message": "API key not configured"}


def test_test_google_success():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.models.list.return_value = [MagicMock()]
        result = _test_google("sk-test")

    mock_client_cls.assert_called_once_with(api_key="sk-test")
    mock_client.models.list.assert_called_once()
    assert result == {"ok": True, "message": "Connected"}


def test_test_google_error():
    with patch("google.genai.Client", side_effect=RuntimeError("boom")):
        result = _test_google("sk-test")
    assert result == {"ok": False, "message": "boom"}
