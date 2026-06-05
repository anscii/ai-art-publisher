import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image
from app.routers.series import series_to_detail
from app.routers.settings import get_or_create_settings
from app.schemas import AIFixKeepRequest, AIFixPreviewResponse, AIFixRequest, SeriesDetail
from app.services.storage import get_storage_from_settings

logger = logging.getLogger("app.image_ai_fix")
router = APIRouter(tags=["image_ai_fix"])

_TEMP_KEY_RE = re.compile(r"^tmp/[0-9a-fA-F-]{36}\.(png|jpe?g)$")
_ALLOWED_EXTS = {"png", "jpg", "jpeg"}


def _content_type_from_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else "jpg"
    return "image/png" if ext == "png" else "image/jpeg"


@router.delete("/api/images/ai-fix/tmp", status_code=204)
def ai_fix_discard(
    temp_key: str,
    db: Session = Depends(get_db),
) -> None:
    if not _TEMP_KEY_RE.match(temp_key):
        raise HTTPException(status_code=400, detail="Invalid temp_key")
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)
    storage.delete(temp_key)


@router.post("/api/images/{image_id}/ai-fix", response_model=AIFixPreviewResponse)
def ai_fix_preview(
    image_id: str,
    body: AIFixRequest,
    db: Session = Depends(get_db),
) -> AIFixPreviewResponse:
    img = db.get(Image, image_id)
    if not img or img.deleted_at:
        raise HTTPException(status_code=404, detail="Image not found")

    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    from app.config import get_config

    if get_config().fake_ai:
        fake_bytes = storage.download_bytes(img.r2_key)
        temp_key = f"tmp/{uuid.uuid4()}.png"
        storage.upload_bytes(fake_bytes, temp_key, "image/png")
        return AIFixPreviewResponse(
            preview_url=storage.public_url(temp_key),
            temp_key=temp_key,
        )

    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")

    image_bytes = storage.download_bytes(img.r2_key)
    content_type = _content_type_from_key(img.r2_key)

    from app.services.ai.image_edit import edit_image

    try:
        edited_bytes = edit_image(settings.openai_api_key, image_bytes, content_type, body.hint)
    except Exception as exc:
        logger.exception("Image edit failed for image %s", image_id)
        raise HTTPException(status_code=502, detail=f"Image edit failed: {exc}") from exc

    temp_key = f"tmp/{uuid.uuid4()}.png"
    storage.upload_bytes(edited_bytes, temp_key, "image/png")

    return AIFixPreviewResponse(
        preview_url=storage.public_url(temp_key),
        temp_key=temp_key,
    )


@router.post("/api/images/{image_id}/ai-fix/keep", response_model=SeriesDetail)
def ai_fix_keep(
    image_id: str,
    body: AIFixKeepRequest,
    db: Session = Depends(get_db),
) -> SeriesDetail:
    if not _TEMP_KEY_RE.match(body.temp_key):
        raise HTTPException(status_code=400, detail="Invalid temp_key")

    img = db.get(Image, image_id)
    if not img or img.deleted_at:
        raise HTTPException(status_code=404, detail="Image not found")

    series = img.series
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    raw_ext = body.temp_key.rsplit(".", 1)[-1].lower() if "." in body.temp_key else "png"
    ext = raw_ext if raw_ext in _ALLOWED_EXTS else "png"
    perm_key = f"images/{uuid.uuid4()}.{ext}"

    storage.copy(body.temp_key, perm_key)
    storage.delete(body.temp_key)

    source_idx = img.order_index
    for other in series.images:
        if other.deleted_at is None and other.id != img.id and other.order_index > source_idx:
            other.order_index += 1

    new_img = Image(
        series_id=series.id,
        r2_key=perm_key,
        original_filename=perm_key.split("/")[-1],
        order_index=source_idx + 1,
    )
    db.add(new_img)
    db.commit()
    db.refresh(series)

    return series_to_detail(series, db)
