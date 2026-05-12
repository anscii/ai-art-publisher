import json
from typing import Any

import anthropic as _anthropic

from app.services.ai.base import (
    SYSTEM_PROMPT,
    AIProvider,
    AIVariantData,
    attach_usage,
    build_user_text,
    extract_json,
)
from app.services.ai.catalogue import calc_cost


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = _anthropic.Anthropic(api_key=api_key)

    def generate_variants(
        self, images_b64: list[str], model: str, hint: str | None = None
    ) -> list[AIVariantData]:
        content = []
        for b64 in images_b64[:4]:
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                }
            )
        content.append({"type": "text", "text": build_user_text(images_b64, hint)})

        messages: list[Any] = [{"role": "user", "content": content}]
        resp = self._client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        block = resp.content[0]
        assert isinstance(block, _anthropic.types.TextBlock)
        raw = json.loads(extract_json(block.text))
        variants = [AIVariantData(**v) for v in raw]
        attach_usage(
            variants,
            resp.usage.input_tokens,
            resp.usage.output_tokens,
            calc_cost(model, resp.usage.input_tokens, resp.usage.output_tokens),
        )
        return variants
