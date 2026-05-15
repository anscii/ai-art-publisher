import logging
from typing import Any

import openai as _openai

from app.services.ai.base import (
    SYSTEM_PROMPT,
    AIProvider,
    AIVariantData,
    attach_usage,
    build_user_text,
    parse_ai_response,
)
from app.services.ai.catalogue import calc_cost

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = _openai.OpenAI(api_key=api_key)

    def _call_api(self, model: str, messages: list[Any]) -> Any:
        return self._client.chat.completions.create(
            model=model, messages=messages, max_completion_tokens=2048, temperature=1.0
        )

    def generate_variants(
        self, images_b64: list[str], model: str, hint: str | None = None
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        if logger.isEnabledFor(logging.DEBUG):
            import json

            logger.debug(
                "openai request | model=%s | messages=%s",
                model,
                json.dumps(messages, ensure_ascii=False),
            )
        resp = self._call_api(model, messages)
        text = resp.choices[0].message.content
        assert text is not None
        logger.debug("openai response | model=%s | text=%s", model, text)
        raw = parse_ai_response(text, "openai", model)
        variants = [AIVariantData(**v) for v in raw]
        assert resp.usage is not None
        attach_usage(
            variants,
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
            calc_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens),
        )
        return variants
