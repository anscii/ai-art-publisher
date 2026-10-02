import base64
import logging
from io import BytesIO
from typing import Any

from app.routers.generate import _call_with_timeout
from app.services.ai.catalogue import calc_image_edit_cost

logger = logging.getLogger(__name__)

_IMAGE_EDIT_TIMEOUT = 120


def _edit_openai(api_key: str, model: str, image_bytes: bytes, content_type: str, hint: str):
    import openai

    client = openai.OpenAI(api_key=api_key)
    ext = "png" if "png" in content_type else "jpg"
    resp = client.images.edit(
        model=model,
        image=(f"image.{ext}", BytesIO(image_bytes), content_type),
        prompt=hint,
        n=1,
    )
    if not resp.data or not resp.data[0].b64_json:
        raise ValueError("OpenAI returned no image data")
    u = resp.usage
    cost = 0.0
    if u:
        d = u.input_tokens_details
        cost = calc_image_edit_cost(model, d.text_tokens, d.image_tokens, u.output_tokens)
    return base64.b64decode(resp.data[0].b64_json), cost


def _edit_google(api_key: str, model: str, image_bytes: bytes, content_type: str, hint: str):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts: list[Any] = [
        types.Part.from_bytes(data=image_bytes, mime_type=content_type),
        types.Part.from_text(text=hint),
    ]
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    out: bytes | None = None
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else None) or []:
            if part.inline_data and part.inline_data.data:
                out = part.inline_data.data
                break
        if out:
            break
    if not out:
        raise ValueError("Google returned no image data")
    u = resp.usage_metadata
    cost = 0.0
    if u:
        # ponytail: text/image input priced the same for Gemini image models, no modality split
        cost = calc_image_edit_cost(
            model, u.prompt_token_count or 0, 0, u.candidates_token_count or 0
        )
    return out, cost


_BACKENDS = {"openai": _edit_openai, "google": _edit_google}


def edit_image(
    provider: str, api_key: str, model: str, image_bytes: bytes, content_type: str, hint: str
) -> tuple[bytes, float]:
    """Edit an image with the given model. Returns (image bytes, cost in USD)."""
    fn = _BACKENDS[provider]
    return _call_with_timeout(
        fn, api_key, model, image_bytes, content_type, hint, timeout=_IMAGE_EDIT_TIMEOUT
    )
