import json
from typing import Any

import openai as _openai

from app.services.ai.base import (
    SYSTEM_PROMPT,
    AIProvider,
    AIVariantData,
    build_user_text,
    extract_json,
)


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
        resp = self._client.chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=messages,
        )
        text = resp.choices[0].message.content
        assert text is not None
        raw = json.loads(extract_json(text))
        return [AIVariantData(**v) for v in raw]
