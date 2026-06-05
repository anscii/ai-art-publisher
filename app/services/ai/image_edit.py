import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


def edit_image(api_key: str, image_bytes: bytes, content_type: str, hint: str) -> bytes:
    """Call OpenAI gpt-image-1 edit endpoint. Returns PNG bytes."""
    import openai

    client = openai.OpenAI(api_key=api_key)
    ext = "png" if "png" in content_type else "jpg"
    resp = client.images.edit(
        model="gpt-image-1",
        image=(f"image.{ext}", BytesIO(image_bytes), content_type),
        prompt=hint,
        n=1,
    )
    if not resp.data:
        raise ValueError("OpenAI returned no image data")
    b64 = resp.data[0].b64_json
    if not b64:
        raise ValueError("OpenAI returned no base64 image data")
    return base64.b64decode(b64)
