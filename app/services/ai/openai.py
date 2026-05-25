import logging
from typing import Any

import openai as _openai

from app.services.ai.base import (
    MAX_OUTPUT_TOKENS,
    AIProvider,
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


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = _openai.OpenAI(api_key=api_key)

    def _call_api(self, model: str, messages: list[Any], response_format: Any = None) -> Any:
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            temperature=1.0,
        )
        if response_format is not None:
            kwargs["response_format"] = response_format
        return self._client.chat.completions.create(**kwargs)

    def _step1_response_format(self, num_variants: int, language: str) -> Any:
        """Return a response_format for step-1 calls; None means no constraint."""
        return None

    def _step2_response_format(self, language: str) -> Any:
        """Return a response_format for step-2 calls; None means no constraint."""
        return None

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
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )
        content.append({"type": "text", "text": build_user_text(images_b64, hint)})

        messages: list[Any] = [
            {"role": "system", "content": build_step1_system_prompt(num_variants, language)},
            {"role": "user", "content": content},
        ]

        if logger.isEnabledFor(logging.DEBUG):
            import json

            logger.debug(
                "openai request | model=%s | messages=%s",
                model,
                json.dumps(messages, ensure_ascii=False),
            )
        resp = self._call_api(model, messages, self._step1_response_format(num_variants, language))
        text = resp.choices[0].message.content
        assert text is not None
        logger.debug("openai response | model=%s | text=%s", model, text)
        raw = parse_ai_response(text, "openai", model)
        variants = [AIVariantData.from_llm_dict(v) for v in raw]
        assert resp.usage is not None
        attach_usage(
            variants,
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
            calc_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens),
        )
        return variants

    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ) -> AIVariantData:
        messages: list[Any] = [
            {"role": "system", "content": build_step2_system_prompt(language)},
            {"role": "user", "content": build_step2_user_text(description, language, hint)},
        ]
        if logger.isEnabledFor(logging.DEBUG):
            import json

            logger.debug(
                "openai expand request | model=%s | language=%s | messages=%s",
                model,
                language,
                json.dumps(messages, ensure_ascii=False),
            )
        resp = self._call_api(model, messages, self._step2_response_format(language))
        text = resp.choices[0].message.content
        assert text is not None
        logger.debug("openai expand response | model=%s | text=%s", model, text)
        raw = parse_ai_object(text, "openai", model)
        data = AIVariantData.from_llm_dict(raw)
        if language == "en":
            data.description_en = description
        else:
            data.description_ru = description
        assert resp.usage is not None
        attach_usage(
            [data],
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
            calc_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens),
        )
        return data
