from typing import Any

import openai as _openai

from app.services.ai.base import MAX_OUTPUT_TOKENS
from app.services.ai.openai import OpenAIProvider

# JSON schema for step-1 (array of N variant drafts, one description key each).
# Built dynamically — language determines the key name.
_STEP1_ITEM_PROPS = {
    "en": {"description_en": {"type": "string"}},
    "ru": {"description_ru": {"type": "string"}},
}
_STEP1_ITEM_REQUIRED = {
    "en": ["description_en"],
    "ru": ["description_ru"],
}

# JSON schema for step-2 (full variant object, secondary description key varies by language).
_STEP2_SECONDARY_KEY = {"en": "description_ru", "ru": "description_en"}

_INSTAGRAM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "seo": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["seo", "tags"],
    "additionalProperties": False,
}

_PINTEREST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "board": {"type": "string"},
    },
    "required": ["title", "description", "board"],
    "additionalProperties": False,
}

_ARCHIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "world_keywords": {"type": "array", "items": {"type": "string"}},
        "visual_keywords": {"type": "array", "items": {"type": "string"}},
        "mood_keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["world_keywords", "visual_keywords", "mood_keywords"],
    "additionalProperties": False,
}


def _step1_schema(num_variants: int, language: str) -> dict[str, Any]:
    lang = language if language in _STEP1_ITEM_PROPS else "en"
    item: dict[str, Any] = {
        "type": "object",
        "properties": _STEP1_ITEM_PROPS[lang],
        "required": _STEP1_ITEM_REQUIRED[lang],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "variants_step1",
            "strict": True,
            "schema": {
                "type": "array",
                "items": item,
                "minItems": num_variants,
                "maxItems": num_variants,
            },
        },
    }


def _step2_schema(language: str) -> dict[str, Any]:
    lang = language if language in _STEP2_SECONDARY_KEY else "en"
    secondary_key = _STEP2_SECONDARY_KEY[lang]
    props: dict[str, Any] = {
        "title": {"type": "string"},
        "title_ru": {"type": "string"},
        secondary_key: {"type": "string"},
        "instagram": _INSTAGRAM_SCHEMA,
        "pinterest": _PINTEREST_SCHEMA,
        "archive_classification": _ARCHIVE_SCHEMA,
        "tags_telegram": {"type": "array", "items": {"type": "string"}},
    }
    required = [
        "title",
        "title_ru",
        secondary_key,
        "instagram",
        "pinterest",
        "archive_classification",
        "tags_telegram",
    ]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "variant_step2",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


class OpenRouterProvider(OpenAIProvider):
    def __init__(self, api_key: str):
        self._client = _openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://ai-art-publisher.fly.dev",
                "X-Title": "AI Art Publisher",
            },
        )
        self._last_resp_model: str | None = None

    def _call_api(self, model: str, messages: list[Any], response_format: Any = None) -> Any:
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=1.0,
            extra_body={"plugins": [{"id": "response-healing"}]},
        )
        if response_format is not None:
            kwargs["response_format"] = response_format
        resp = self._client.chat.completions.create(**kwargs)
        self._last_resp_model = resp.model
        return resp

    def _step1_response_format(self, num_variants: int, language: str) -> Any:
        return _step1_schema(num_variants, language)

    def _step2_response_format(self, language: str) -> Any:
        return _step2_schema(language)

    def generate_variants(
        self,
        images_b64: list[Any],
        model: str,
        hint: str | None = None,
        num_variants: int = 3,
        language: str = "en",
    ) -> list:
        from app.services.ai.base import AIVariantData as _AVD  # noqa: F401

        variants = super().generate_variants(images_b64, model, hint, num_variants, language)
        for v in variants:
            v.actual_model = self._last_resp_model
        return variants

    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ):
        vd = super().expand_variant(description, language, model, hint)
        vd.actual_model = self._last_resp_model
        return vd
