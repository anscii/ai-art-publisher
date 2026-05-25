"""Tests for OpenRouterProvider structured-output and response-healing additions."""

from unittest.mock import MagicMock, patch

from app.services.ai.openrouter import (
    OpenRouterProvider,
    _step1_schema,
    _step2_schema,
)

# ── _step1_schema ─────────────────────────────────────────────────────────────


def test_step1_schema_english_has_description_en():
    s = _step1_schema(3, "en")
    assert s["type"] == "json_schema"
    js = s["json_schema"]
    assert js["name"] == "variants_step1"
    assert js["strict"] is True
    item = js["schema"]["items"]
    assert "description_en" in item["properties"]
    assert "description_ru" not in item["properties"]
    assert item["required"] == ["description_en"]
    assert item["additionalProperties"] is False


def test_step1_schema_russian_has_description_ru():
    s = _step1_schema(2, "ru")
    item = s["json_schema"]["schema"]["items"]
    assert "description_ru" in item["properties"]
    assert "description_en" not in item["properties"]
    assert item["required"] == ["description_ru"]


def test_step1_schema_min_max_items_match_num_variants():
    for n in (1, 3, 5):
        schema = _step1_schema(n, "en")["json_schema"]["schema"]
        assert schema["minItems"] == n
        assert schema["maxItems"] == n


def test_step1_schema_unknown_language_falls_back_to_en():
    s = _step1_schema(3, "xx")
    item = s["json_schema"]["schema"]["items"]
    assert "description_en" in item["properties"]


# ── _step2_schema ─────────────────────────────────────────────────────────────


def test_step2_schema_en_has_description_ru():
    s = _step2_schema("en")
    schema = s["json_schema"]["schema"]
    assert "description_ru" in schema["properties"]
    assert "description_en" not in schema["properties"]
    assert "description_ru" in schema["required"]


def test_step2_schema_ru_has_description_en():
    s = _step2_schema("ru")
    schema = s["json_schema"]["schema"]
    assert "description_en" in schema["properties"]
    assert "description_ru" not in schema["properties"]


def test_step2_schema_always_has_required_keys():
    for lang in ("en", "ru"):
        schema = _step2_schema(lang)["json_schema"]["schema"]
        required = set(schema["required"])
        assert {
            "title",
            "title_ru",
            "instagram",
            "pinterest",
            "archive_classification",
            "tags_telegram",
        }.issubset(required)


def test_step2_schema_nested_objects_have_no_additional_properties():
    schema = _step2_schema("en")["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["instagram"]["additionalProperties"] is False
    assert schema["properties"]["pinterest"]["additionalProperties"] is False
    assert schema["properties"]["archive_classification"]["additionalProperties"] is False


def test_step2_schema_instagram_required_keys():
    props = _step2_schema("en")["json_schema"]["schema"]["properties"]
    ig = props["instagram"]
    assert set(ig["required"]) == {"seo", "tags"}


def test_step2_schema_archive_required_keys():
    props = _step2_schema("en")["json_schema"]["schema"]["properties"]
    arch = props["archive_classification"]
    assert set(arch["required"]) == {"world_keywords", "visual_keywords", "mood_keywords"}


def test_step2_schema_is_strict():
    assert _step2_schema("en")["json_schema"]["strict"] is True


def test_step2_schema_unknown_language_falls_back_to_en():
    s = _step2_schema("xx")
    schema = s["json_schema"]["schema"]
    assert "description_ru" in schema["properties"]


# ── OpenRouterProvider._call_api ─────────────────────────────────────────────


def _make_provider():
    with patch("openai.OpenAI"):
        p = OpenRouterProvider(api_key="sk-test")
    return p


def test_call_api_sends_response_healing_plugin():
    provider = _make_provider()
    mock_resp = MagicMock()
    provider._client.chat.completions.create = MagicMock(return_value=mock_resp)

    provider._call_api("model-x", [{"role": "user", "content": "hi"}])

    args, kwargs = provider._client.chat.completions.create.call_args
    extra_body = kwargs.get("extra_body", {})
    assert extra_body.get("plugins") == [{"id": "response-healing"}]


def test_call_api_includes_response_format_when_provided():
    provider = _make_provider()
    provider._client.chat.completions.create = MagicMock(return_value=MagicMock())
    fmt = {"type": "json_schema", "json_schema": {"name": "x", "strict": True, "schema": {}}}

    provider._call_api("model-x", [], response_format=fmt)

    _, kwargs = provider._client.chat.completions.create.call_args
    assert kwargs["response_format"] == fmt


def test_call_api_omits_response_format_when_none():
    provider = _make_provider()
    provider._client.chat.completions.create = MagicMock(return_value=MagicMock())

    provider._call_api("model-x", [], response_format=None)

    _, kwargs = provider._client.chat.completions.create.call_args
    assert "response_format" not in kwargs


# ── OpenRouterProvider format hooks ──────────────────────────────────────────


def test_step1_response_format_returns_schema():
    provider = _make_provider()
    fmt = provider._step1_response_format(3, "en")
    assert fmt is not None
    assert fmt["type"] == "json_schema"


def test_step2_response_format_returns_schema():
    provider = _make_provider()
    fmt = provider._step2_response_format("en")
    assert fmt is not None
    assert fmt["type"] == "json_schema"


# ── OpenAIProvider base hooks return None (no schema) ────────────────────────


def test_openai_provider_step1_format_is_none():
    from app.services.ai.openai import OpenAIProvider

    with patch("openai.OpenAI"):
        p = OpenAIProvider(api_key="sk-test")
    assert p._step1_response_format(3, "en") is None


def test_openai_provider_step2_format_is_none():
    from app.services.ai.openai import OpenAIProvider

    with patch("openai.OpenAI"):
        p = OpenAIProvider(api_key="sk-test")
    assert p._step2_response_format("en") is None
