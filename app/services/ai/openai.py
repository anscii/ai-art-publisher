import json
from typing import Any

import openai as _openai

from app.services.ai.base import (
    SYSTEM_PROMPT,
    AIProvider,
    AIVariantData,
    attach_usage,
    build_user_text,
    extract_json,
)
from app.services.ai.catalogue import calc_cost

_MAX_COMPLETION_TOKEN_MODELS = frozenset({"gpt-5.4", "gpt-5.4-mini"})


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = _openai.OpenAI(api_key=api_key)

    def generate_variants(
        self, images_b64: list[str], model: str, hint: str | None = None
    ) -> list[AIVariantData]:
        content = []
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

        if model in _MAX_COMPLETION_TOKEN_MODELS:
            resp = self._client.chat.completions.create(
                model=model, messages=messages, max_completion_tokens=2048
            )
        else:
            resp = self._client.chat.completions.create(
                model=model, messages=messages, max_tokens=2048
            )
        text = resp.choices[0].message.content
        assert text is not None
        raw = json.loads(extract_json(text))
        variants = [AIVariantData(**v) for v in raw]
        assert resp.usage is not None
        attach_usage(
            variants,
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
            calc_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens),
        )
        return variants
