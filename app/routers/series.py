import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import AIVariant, Image, Post, PostImage, Series, Story
from app.routers.posts import post_to_resp
from app.routers.settings import get_or_create_settings
from app.schemas import (
    AIVariantResponse,
    CollectionRef,
    ImageResponse,
    SaveQueueBody,
    SeriesCreate,
    SeriesDetail,
    SeriesListItem,
    SeriesListResponse,
    SeriesUpdate,
)
from app.services.storage import get_public_base_url

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


def variant_to_resp(v: AIVariant, used_in_posts: bool = False) -> AIVariantResponse:
    return AIVariantResponse(
        id=v.id,
        series_id=v.series_id,
        provider=v.provider,
        model=v.model,
        title=v.title,
        title_ru=v.title_ru,
        description_en=v.description_en,
        description_ru=v.description_ru,
        tags_instagram=json.loads(v.tags_instagram),
        tags_telegram=json.loads(v.tags_telegram),
        hint=v.hint,
        cost_usd=v.cost_usd,
        generated_at=v.generated_at,
        instagram_seo=v.instagram_seo,
        pinterest_title=v.pinterest_title,
        pinterest_description=v.pinterest_description,
        pinterest_board=v.pinterest_board,
        archive_metadata=json.loads(v.archive_metadata) if v.archive_metadata else None,
        draft_id=v.draft_id,
        used_in_posts=used_in_posts,
    )


def series_to_detail(s: Series, db: Session) -> SeriesDetail:
    settings = get_or_create_settings(db)
    base_url = get_public_base_url(settings)
    images = sorted([i for i in s.images if i.deleted_at is None], key=lambda i: i.order_index)
    variants = sorted(s.ai_variants, key=lambda v: v.generated_at, reverse=True)
    active_posts = db.scalars(
        select(Post)
        .options(
            selectinload(Post.post_images).selectinload(PostImage.image),
            selectinload(Post.story).selectinload(Story.frames),
        )
        .where(Post.series_id == s.id, Post.deleted_at.is_(None))
        .order_by(Post.created_at)
    ).all()
    collection_ref = (
        CollectionRef(
            id=s.collection.id,
            name=s.collection.name,
            name_ru=s.collection.name_ru,
            collection_index=s.collection_index,
            collection_number=s.collection_number,
        )
        if s.collection and s.collection.deleted_at is None
        else None
    )
    return SeriesDetail(
        id=s.id,
        original_folder_name=s.original_folder_name,
        name=s.name,
        title=s.title,
        title_ru=s.title_ru,
        description_en=s.description_en,
        description_ru=s.description_ru,
        tags_instagram=json.loads(s.tags_instagram),
        tags_telegram=json.loads(s.tags_telegram),
        status=s.status,
        collection=collection_ref,
        chosen_variant_id=s.chosen_variant_id,
        collection_index=s.collection_index,
        collection_number=s.collection_number,
        created_at=s.created_at,
        images=[image_to_resp(img, base_url) for img in images],
        ai_variants=[
            variant_to_resp(
                v, used_in_posts=v.id in {p.variant_id for p in active_posts if p.variant_id}
            )
            for v in variants
        ],
        posts=[post_to_resp(p) for p in active_posts],
    )


def series_to_list_item(s: Series, base_url: str) -> SeriesListItem:
    active = sorted([i for i in s.images if i.deleted_at is None], key=lambda i: i.order_index)
    cover_url = f"{base_url}/{active[0].r2_key}" if active and base_url else None
    coll = s.collection if s.collection and s.collection.deleted_at is None else None
    return SeriesListItem(
        id=s.id,
        original_folder_name=s.original_folder_name,
        name=s.name,
        title=s.title,
        status=s.status,
        collection_name=coll.name if coll else None,
        collection_name_ru=coll.name_ru if coll else None,
        collection_number=s.collection_number,
        created_at=s.created_at,
        image_count=len(active),
        posted_count=sum(1 for i in active if i.status == "posted"),
        cover_url=cover_url,
    )


def _assign_collection_index(s: Series, new_cid: str | None, db: Session) -> None:
    old_cid = s.collection_id
    if new_cid == old_cid:
        return
    if new_cid is None:
        s.collection_index = None
        s.collection_number = None
    else:
        max_idx = (
            db.scalar(
                select(func.max(Series.collection_index)).where(
                    Series.collection_id == new_cid,
                    Series.deleted_at.is_(None),
                )
            )
            or 0
        )
        s.collection_index = max_idx + 1
        if s.collection_number is None:
            s.collection_number = str(s.collection_index)


@router.post("", status_code=201)
def create_series(body: SeriesCreate, db: Session = Depends(get_db)) -> SeriesDetail:
    s = Series(
        name=body.name or body.title,
        title=body.title,
        status=body.status,
        original_folder_name=body.original_folder_name,
        created_at=body.created_at or datetime.now(UTC),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return series_to_detail(s, db)


@router.get("")
def list_series(
    status: str | None = Query(None),
    search: str | None = Query(None),
    collection_id: str | None = Query(None),
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
    if search:
        q = q.where(Series.name.ilike(f"%{search}%") | Series.title.ilike(f"%{search}%"))
    if collection_id:
        q = q.where(Series.collection_id == collection_id)
    q = q.order_by(Series.created_at.asc())
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.offset((page - 1) * limit).limit(limit)).all()
    settings = get_or_create_settings(db)
    base_url = get_public_base_url(settings)
    return SeriesListResponse(
        items=[series_to_list_item(s, base_url) for s in rows],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/unsorted")
def get_or_create_unsorted(db: Session = Depends(get_db)) -> SeriesDetail:
    s = db.scalars(
        select(Series).where(Series.title == "Unsorted", Series.deleted_at.is_(None))
    ).first()
    if not s:
        s = Series(name="Unsorted", title="Unsorted", status="new")
        db.add(s)
        db.commit()
        db.refresh(s)
    return series_to_detail(s, db)


@router.put("/{series_id}/queue")
def save_queue(series_id: str, body: SaveQueueBody, db: Session = Depends(get_db)) -> SeriesDetail:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    selected = set(body.image_ids)
    for img in s.images:
        if img.deleted_at or img.status in ("posted", "skip"):
            continue
        img.status = "queued" if img.id in selected else "pending"
    db.commit()
    return series_to_detail(s, db)


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
    updates = body.model_dump(exclude_unset=True)
    if "collection_id" in updates:
        _assign_collection_index(s, updates["collection_id"], db)
    for field, value in updates.items():
        if field in ("tags_instagram", "tags_telegram"):
            value = json.dumps(value)
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return series_to_detail(s, db)


@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    s.deleted_at = datetime.now(UTC)
    db.commit()
    return {"deleted": series_id}
