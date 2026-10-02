"""AnthropicProvider: thinking-enabled models put a ``thinking`` block before the text."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.ai.anthropic import AnthropicProvider
from app.services.ai.base import AIResponseError, parse_ai_object, parse_ai_response

_USAGE = SimpleNamespace(input_tokens=10, output_tokens=5)


def _resp(*blocks, stop_reason="end_turn", stop_details=None):
    return SimpleNamespace(
        content=list(blocks), stop_reason=stop_reason, stop_details=stop_details, usage=_USAGE
    )


def _thinking():
    return SimpleNamespace(type="thinking", thinking="", signature="sig")


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _provider(resp):
    p = AnthropicProvider(api_key="sk-test")
    p._client = MagicMock()
    p._client.messages.create.return_value = resp
    return p


def test_generate_variants_skips_thinking_block():
    p = _provider(_resp(_thinking(), _text('```json\n[{"description_en": "A. B."}]\n```')))
    variants = p.generate_variants([], "claude-sonnet-5-5", hint="sea", num_variants=1)
    assert len(variants) == 1
    assert variants[0].description_en.startswith("A.")


def test_expand_variant_skips_thinking_block():
    p = _provider(_resp(_thinking(), _text('{"title": "T", "title_ru": "Т"}')))
    data = p.expand_variant("desc", "en", "claude-opus-5-5")
    assert data.title == "T"
    assert data.description_en == "desc"


def test_no_text_block_raises_readable_error():
    p = _provider(_resp(_thinking(), stop_reason="max_tokens"))
    with pytest.raises(AIResponseError, match="claude-sonnet-5-5 returned no text.*max_tokens"):
        p.generate_variants([], "claude-sonnet-5-5", hint="sea")


def test_refusal_explanation_in_error():
    details = SimpleNamespace(category="cyber", explanation="nope")
    p = _provider(_resp(_thinking(), stop_reason="refusal", stop_details=details))
    with pytest.raises(AIResponseError, match="refusal: nope"):
        p.expand_variant("desc", "en", "claude-opus-5-5")


@pytest.mark.parametrize("fn", [parse_ai_response, parse_ai_object])
def test_invalid_json_raises_readable_error(fn):
    with pytest.raises(
        AIResponseError, match="anthropic claude-x returned a response that is not valid JSON"
    ):
        fn("not json at all", "anthropic", "claude-x")
