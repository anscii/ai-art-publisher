import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIVariant, Image, Series
from app.routers.settings import get_or_create_settings
from app.schemas import (
    AIVariantResponse,
    ImageResponse,
    SeriesCreate,
    SeriesDetail,
    SeriesListItem,
    SeriesListResponse,
    SeriesUpdate,
)

router = APIRouter(prefix="/api/series", tags=["series"])


def image_to_resp(img: Image, base_url: str) -> ImageResponse:
    return ImageResponse(
        id=img.id,
        series_id=img.series_id,
        r2_key=img.r2_key,
        original_filename=img.original_filename,
        original_created_at=img.original_created_at,
        order_index=img.order_index,
        status=img.status,
        uploaded_at=img.uploaded_at,
        deleted_at=img.deleted_at,
        public_url=f"{base_url}/{img.r2_key}" if base_url else img.r2_key,
    )


def variant_to_resp(v: AIVariant) -> AIVariantResponse:
    return AIVariantResponse(
        id=v.id,
        series_id=v.series_id,
        provider=v.provider,
        model=v.model,
        title=v.title,
        description_en=v.description_en,
        description_ru=v.description_ru,
        tags_instagram=json.loads(v.tags_instagram),
        tags_telegram=json.loads(v.tags_telegram),
        generated_at=v.generated_at,
    )


def series_to_detail(s: Series, db: Session) -> SeriesDetail:
    settings = get_or_create_settings(db)
    base_url = settings.r2_public_base_url.rstrip("/")
    images = sorted([i for i in s.images if i.deleted_at is None], key=lambda i: i.order_index)
    variants = sorted(s.ai_variants, key=lambda v: v.generated_at, reverse=True)
    return SeriesDetail(
        id=s.id,
        original_folder_name=s.original_folder_name,
        title=s.title,
        description_en=s.description_en,
        description_ru=s.description_ru,
        tags_instagram=json.loads(s.tags_instagram),
        tags_telegram=json.loads(s.tags_telegram),
        status=s.status,
        notes=s.notes,
        needs_review=s.needs_review,
        review_reason=s.review_reason,
        created_at=s.created_at,
        scheduled_at=s.scheduled_at,
        scheduled_targets=json.loads(s.scheduled_targets),
        posted_to_telegram_at=s.posted_to_telegram_at,
        posted_to_instagram_at=s.posted_to_instagram_at,
        images=[image_to_resp(img, base_url) for img in images],
        ai_variants=[variant_to_resp(v) for v in variants],
    )


def series_to_list_item(s: Series, base_url: str) -> SeriesListItem:
    active = sorted([i for i in s.images if i.deleted_at is None], key=lambda i: i.order_index)
    cover_url = f"{base_url}/{active[0].r2_key}" if active and base_url else None
    return SeriesListItem(
        id=s.id,
        original_folder_name=s.original_folder_name,
        title=s.title,
        status=s.status,
        needs_review=s.needs_review,
        created_at=s.created_at,
        scheduled_at=s.scheduled_at,
        posted_to_telegram_at=s.posted_to_telegram_at,
        posted_to_instagram_at=s.posted_to_instagram_at,
        image_count=len(active),
        cover_url=cover_url,
    )


@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db)) -> SeriesDetail:
    s = Series(
        title=body.title,
        status=body.status,
        original_folder_name=body.original_folder_name,
        created_at=body.created_at or datetime.utcnow(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return series_to_detail(s, db)


@router.get("")
def list_series(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SeriesListResponse:
    q = select(Series).where(Series.deleted_at.is_(None))
    if status:
        statuses = [s.strip() for s in status.split(",")]
        q = q.where(Series.status.in_(statuses))
    else:
        q = q.where(Series.status != "skip")
    q = q.order_by(Series.created_at.desc())
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.offset((page - 1) * limit).limit(limit)).all()
    settings = get_or_create_settings(db)
    base_url = settings.r2_public_base_url.rstrip("/")
    return SeriesListResponse(
        items=[series_to_list_item(s, base_url) for s in rows],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db)) -> SeriesDetail:
    s = db.get(Series, series_id)
    if not s or s.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Series not found")
    return series_to_detail(s, db)


@router.put("/{series_id}")
def update_series(
    series_id: str, body: SeriesUpdate, db: Session = Depends(get_db)
) -> SeriesDetail:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    for field, value in body.model_dump(exclude_none=True).items():
        if field in ("tags_instagram", "tags_telegram"):
            value = json.dumps(value)
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return series_to_detail(s, db)


@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db)):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    s.deleted_at = datetime.utcnow()
    db.commit()
    return {"deleted": series_id}
