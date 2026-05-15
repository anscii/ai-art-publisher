import base64
import io
import logging
from typing import Any

import google.generativeai as genai

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
        logger.debug(
            "google request | model=%s | parts(count)=%d | text=%s",
            model,
            len(parts),
            parts[-1] if parts else "",
        )
        resp = m.generate_content(
            parts,
            generation_config={
                "temperature": 1.0,
                "top_p": 0.95,
            },
        )
        logger.debug("google response | model=%s | text=%s", model, resp.text)
        raw = parse_ai_response(resp.text, "google", model)
        variants = [AIVariantData.from_llm_dict(v) for v in raw]
        u = resp.usage_metadata
        attach_usage(
            variants,
            u.prompt_token_count,
            u.candidates_token_count,
            calc_cost(model, u.prompt_token_count, u.candidates_token_count),
        )
        return variants
