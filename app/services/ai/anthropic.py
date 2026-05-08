import json
from typing import Any

import anthropic as _anthropic

from app.services.ai.base import SYSTEM_PROMPT, AIProvider, AIVariantData


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
        user_text = "Describe this artwork series."
        if hint:
            user_text += f" Additional context: {hint}"
        content.append({"type": "text", "text": user_text})

        messages: list[Any] = [{"role": "user", "content": content}]
        resp = self._client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        block = resp.content[0]
        assert isinstance(block, _anthropic.types.TextBlock)
        raw = json.loads(block.text)
        return [AIVariantData(**v) for v in raw]
