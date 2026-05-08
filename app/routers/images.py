import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image, Series
from app.routers.series import image_to_resp, series_to_detail
from app.routers.settings import get_or_create_settings
from app.schemas import ImageStatusUpdate, MoveImageBody, RegisterImageBody, ReorderImagesBody
from app.services.storage import get_storage_from_settings

router = APIRouter(tags=["images"])

_TS_RE = re.compile(r"^(\d{10,13})")


def _parse_ts(filename: str) -> datetime | None:
    m = _TS_RE.match(filename)
    if not m:
        return None
    ts = int(m.group(1))
    if ts > 10**12:
        ts //= 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def _next_order(series: Series) -> int:
    return max((img.order_index for img in series.images), default=-1) + 1


@router.post("/api/series/{series_id}/images")
async def upload_images(
    series_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)
    results = []
    for file in files:
        data = await file.read()
        ext = (file.filename or "").rsplit(".", 1)[-1] or "jpg"
        key = f"images/{uuid.uuid4()}.{ext}"
        storage.upload_bytes(data, key, file.content_type or "image/jpeg")
        img = Image(
            series_id=series_id,
            r2_key=key,
            original_filename=file.filename or key,
            original_created_at=_parse_ts(file.filename or ""),
            order_index=_next_order(s),
        )
        db.add(img)
        db.flush()
        base_url = settings.r2_public_base_url.rstrip("/")
        results.append(image_to_resp(img, base_url))
    db.commit()
    return results


@router.post("/api/series/{series_id}/images/register")
def register_image(
    series_id: str,
    body: RegisterImageBody,
    db: Session = Depends(get_db),
):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    img = Image(
        series_id=series_id,
        r2_key=body.r2_key,
        original_filename=body.original_filename,
        original_created_at=body.original_created_at,
        order_index=_next_order(s),
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    settings = get_or_create_settings(db)
    return image_to_resp(img, settings.r2_public_base_url.rstrip("/"))


@router.put("/api/series/{series_id}/images/reorder")
def reorder_images(
    series_id: str,
    body: ReorderImagesBody,
    db: Session = Depends(get_db),
):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    images = {img.id: img for img in s.images}
    for idx, img_id in enumerate(body.image_ids):
        if img_id in images:
            images[img_id].order_index = idx
    db.commit()
    return {"reordered": len(body.image_ids)}


@router.put("/api/images/{image_id}/move")
def move_image(
    image_id: str,
    body: MoveImageBody,
    db: Session = Depends(get_db),
):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    target = db.get(Series, body.target_series_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target series not found")
    img.series_id = body.target_series_id
    img.order_index = _next_order(target)
    db.commit()
    return {"moved": image_id, "to": body.target_series_id}


@router.patch("/api/images/{image_id}/status")
def update_image_status(
    image_id: str,
    body: ImageStatusUpdate,
    db: Session = Depends(get_db),
):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    if body.status not in {"pending", "queued", "posted", "skip"}:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    img.status = body.status
    db.commit()
    return series_to_detail(img.series, db)


@router.delete("/api/images/{image_id}")
def delete_image(image_id: str, db: Session = Depends(get_db)):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    settings = get_or_create_settings(db)
    try:
        get_storage_from_settings(settings).delete(img.r2_key)
    except Exception:
        pass
    db.delete(img)
    db.commit()
    return {"deleted": image_id}
