import logging
from typing import Any

import anthropic as _anthropic

from app.services.ai.base import (
    MAX_OUTPUT_TOKENS,
    AIProvider,
    AIResponseError,
    AIVariantData,
    attach_usage,
    build_step1_system_prompt,
    build_step2_system_prompt,
    build_step2_user_text,
    build_user_text,
    parse_ai_object,
    parse_ai_response,
)
from app.services.ai.catalogue import calc_cost

logger = logging.getLogger(__name__)


def _response_text(resp: Any, model: str) -> str:
    """First text block of a Messages response.

    Thinking-enabled models (Sonnet 5.5, Opus 5.5, ...) put a ``thinking`` block
    before the text, so ``content[0]`` is not always text.
    """
    for block in resp.content:
        if getattr(block, "type", None) == "text" and block.text:
            return block.text  # type: ignore[no-any-return]
    detail = resp.stop_reason or "unknown"
    if resp.stop_reason == "refusal" and getattr(resp, "stop_details", None):
        detail = f"refusal: {resp.stop_details.explanation or resp.stop_details.category}"
    raise AIResponseError(f"Anthropic {model} returned no text (stop_reason={detail})")


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = _anthropic.Anthropic(api_key=api_key)

    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
        num_variants: int = 3,
        language: str = "en",
    ) -> list[AIVariantData]:
        content: list[Any] = []
        for b64 in images_b64[:4]:
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                }
            )
        content.append({"type": "text", "text": build_user_text(images_b64, hint)})

        messages: list[Any] = [{"role": "user", "content": content}]
        if logger.isEnabledFor(logging.DEBUG):
            import json

            logger.debug(
                "anthropic request | model=%s | messages=%s",
                model,
                json.dumps(messages, ensure_ascii=False),
            )
        resp = self._client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=build_step1_system_prompt(num_variants, language, style_guide=self.style_guide),
            messages=messages,
        )
        text = _response_text(resp, model)
        logger.debug("anthropic response | model=%s | text=%s", model, text)
        raw = parse_ai_response(text, "anthropic", model)
        variants = [AIVariantData.from_llm_dict(v) for v in raw]
        attach_usage(
            variants,
            resp.usage.input_tokens,
            resp.usage.output_tokens,
            calc_cost(model, resp.usage.input_tokens, resp.usage.output_tokens),
        )
        return variants

    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ) -> AIVariantData:
        content: list[Any] = [
            {"type": "text", "text": build_step2_user_text(description, language, hint)}
        ]
        messages: list[Any] = [{"role": "user", "content": content}]
        if logger.isEnabledFor(logging.DEBUG):
            import json

            logger.debug(
                "anthropic expand request | model=%s | language=%s | messages=%s",
                model,
                language,
                json.dumps(messages, ensure_ascii=False),
            )
        resp = self._client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=build_step2_system_prompt(language, style_guide=self.style_guide),
            messages=messages,
        )
        text = _response_text(resp, model)
        logger.debug("anthropic expand response | model=%s | text=%s", model, text)
        raw = parse_ai_object(text, "anthropic", model)
        data = AIVariantData.from_llm_dict(raw)
        if language == "en":
            data.description_en = description
        else:
            data.description_ru = description
        attach_usage(
            [data],
            resp.usage.input_tokens,
            resp.usage.output_tokens,
            calc_cost(model, resp.usage.input_tokens, resp.usage.output_tokens),
        )
        return data
