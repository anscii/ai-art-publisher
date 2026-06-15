import base64
import io
import logging
from typing import Any

from google import genai
from google.genai import types

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


class GoogleProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
        num_variants: int = 3,
        language: str = "en",
    ) -> list[AIVariantData]:
        import PIL.Image

        parts: list[Any] = []
        for b64 in images_b64[:4]:
            img = PIL.Image.open(io.BytesIO(base64.b64decode(b64)))
            parts.append(img)
        parts.append(build_user_text(images_b64, hint))

        logger.debug(
            "google request | model=%s | parts(count)=%d | text=%s",
            model,
            len(parts),
            parts[-1] if parts else "",
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=build_step1_system_prompt(num_variants, language),
                temperature=1.0,
                top_p=0.95,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        logger.debug("google response | model=%s | text=%s", model, resp.text)
        assert resp.text is not None
        raw = parse_ai_response(resp.text, "google", model)
        variants = [AIVariantData.from_llm_dict(v) for v in raw]
        u = resp.usage_metadata
        assert u is not None
        input_tokens = u.prompt_token_count or 0
        output_tokens = u.candidates_token_count or 0
        attach_usage(
            variants, input_tokens, output_tokens, calc_cost(model, input_tokens, output_tokens)
        )
        return variants

    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ) -> AIVariantData:
        user_text = build_step2_user_text(description, language, hint)
        logger.debug(
            "google expand request | model=%s | language=%s | text=%s", model, language, user_text
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=build_step2_system_prompt(language),
                temperature=1.0,
                top_p=0.95,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        logger.debug("google expand response | model=%s | text=%s", model, resp.text)
        assert resp.text is not None
        raw = parse_ai_object(resp.text, "google", model)
        data = AIVariantData.from_llm_dict(raw)
        if language == "en":
            data.description_en = description
        else:
            data.description_ru = description
        u = resp.usage_metadata
        assert u is not None
        input_tokens = u.prompt_token_count or 0
        output_tokens = u.candidates_token_count or 0
        attach_usage(
            [data], input_tokens, output_tokens, calc_cost(model, input_tokens, output_tokens)
        )
        return data
