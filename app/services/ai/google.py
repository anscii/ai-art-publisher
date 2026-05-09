import base64
import io
import json
from typing import Any

import google.generativeai as genai

from app.services.ai.base import (
    SYSTEM_PROMPT,
    AIProvider,
    AIVariantData,
    build_user_text,
    extract_json,
)


class GoogleProvider(AIProvider):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def generate_variants(
        self, images_b64: list[str], model: str, hint: str | None = None
    ) -> list[AIVariantData]:
        import PIL.Image

        parts: list[Any] = []
        for b64 in images_b64[:4]:
            img = PIL.Image.open(io.BytesIO(base64.b64decode(b64)))
            parts.append(img)
        parts.append(build_user_text(images_b64, hint))

        m = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
        resp = m.generate_content(parts)
        raw = json.loads(extract_json(resp.text))
        return [AIVariantData(**v) for v in raw]
