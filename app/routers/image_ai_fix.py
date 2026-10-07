import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIRequest, Image, User
from app.ownership import get_owned
from app.routers.auth import get_current_user
from app.routers.series import series_to_detail
from app.routers.settings import get_or_create_settings
from app.routers.user_settings import get_user_settings
from app.schemas import AIFixKeepRequest, AIFixPreviewResponse, AIFixRequest, SeriesDetail
from app.services.ai.access import record_request
from app.services.ai.catalogue import DEFAULT_IMAGE_EDIT_MODEL, image_edit_provider
from app.services.storage import get_storage_from_settings

logger = logging.getLogger("app.image_ai_fix")
router = APIRouter(tags=["image_ai_fix"])

_TEMP_KEY_RE = re.compile(r"^tmp/([0-9a-fA-F-]{36})/[0-9a-fA-F-]{36}\.(png|jpe?g)$")
_ALLOWED_EXTS = {"png", "jpg", "jpeg"}


def _check_temp_key(key: str, user: User) -> None:
    m = _TEMP_KEY_RE.match(key)
    if not m or m.group(1) != user.id:
        raise HTTPException(status_code=400, detail="Invalid temp_key")


def _content_type_from_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else "jpg"
    return "image/png" if ext == "png" else "image/jpeg"


@router.delete("/api/images/ai-fix/tmp", status_code=204)
def ai_fix_discard(
    temp_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    _check_temp_key(temp_key, user)
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)
    storage.delete(temp_key)


@router.post("/api/images/{image_id}/ai-fix", response_model=AIFixPreviewResponse)
def ai_fix_preview(
    image_id: str,
    body: AIFixRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIFixPreviewResponse:
    img = get_owned(Image, image_id, user, db)

    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    from app.config import get_config

    if get_config().fake_ai:
        fake_bytes = storage.download_bytes(img.r2_key)
        temp_key = f"tmp/{user.id}/{uuid.uuid4()}.png"
        storage.upload_bytes(fake_bytes, temp_key, "image/png")
        return AIFixPreviewResponse(
            preview_url=storage.public_url(temp_key),
            temp_key=temp_key,
        )

    us = get_user_settings(user.id, db)
    model = body.model or us.image_edit_model or DEFAULT_IMAGE_EDIT_MODEL
    try:
        provider = image_edit_provider(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    api_key = us.openai_api_key if provider == "openai" else us.google_api_key
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Fix with AI needs your own OpenAI or Google key. Add one in Settings.",
        )

    image_bytes = storage.download_bytes(img.r2_key)
    content_type = _content_type_from_key(img.r2_key)

    from app.services.ai.image_edit import edit_image

    try:
        edited_bytes, cost = edit_image(
            provider, api_key, model, image_bytes, content_type, body.hint
        )
    except Exception:
        logger.exception("Image edit failed for image %s", image_id)
        raise HTTPException(status_code=502, detail="Image editing failed. Try again.")

    temp_key = f"tmp/{user.id}/{uuid.uuid4()}.png"
    storage.upload_bytes(edited_bytes, temp_key, "image/png")

    # Own key only, so never counts toward Quota; success only (failed edits cost nothing).
    rid = record_request(
        db,
        user_id=user.id,
        kind="image_fix",
        provider=provider,
        model=model,
        via_default=False,
        limit=0,
    )
    db.flush()  # autoflush is off; make the pending row visible to get()
    db.get(AIRequest, rid).cost_usd = cost  # type: ignore[union-attr]
    db.commit()

    return AIFixPreviewResponse(
        preview_url=storage.public_url(temp_key),
        temp_key=temp_key,
        model=model,
        cost_usd=cost,
    )


@router.post("/api/images/{image_id}/ai-fix/keep", response_model=SeriesDetail)
def ai_fix_keep(
    image_id: str,
    body: AIFixKeepRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SeriesDetail:
    _check_temp_key(body.temp_key, user)

    img = get_owned(Image, image_id, user, db)

    series = img.series
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    raw_ext = body.temp_key.rsplit(".", 1)[-1].lower() if "." in body.temp_key else "png"
    ext = raw_ext if raw_ext in _ALLOWED_EXTS else "png"
    perm_key = f"images/{uuid.uuid4()}.{ext}"

    try:
        storage.copy(body.temp_key, perm_key)
        storage.delete(body.temp_key)
    except Exception:
        logger.exception("Storage promotion failed for temp_key %s", body.temp_key)
        raise HTTPException(status_code=502, detail="Failed to save image. Try again.")

    source_idx = img.order_index
    for other in series.images:
        if other.deleted_at is None and other.id != img.id and other.order_index > source_idx:
            other.order_index += 1

    new_img = Image(
        series_id=series.id,
        r2_key=perm_key,
        original_filename=f"ai-fix-{img.original_filename}",
        order_index=source_idx + 1,
    )
    db.add(new_img)
    db.commit()
    db.refresh(series)

    return series_to_detail(series, db)
