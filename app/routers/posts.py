import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.models import Post, PostImage, Series
from app.routers.settings import get_or_create_settings
from app.schemas import PostBatchCreate, PostResponse, PostResult, PostScheduleRequest, PostUpdate
from app.services.facebook import FacebookService
from app.services.instagram import InstagramService
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["posts"])

VALID_PLATFORMS = {"telegram", "instagram", "facebook"}


def post_to_resp(p: Post) -> PostResponse:
    ordered = sorted(p.post_images, key=lambda pi: pi.order_index)
    return PostResponse(
        id=p.id,
        series_id=p.series_id,
        platform=p.platform,
        title=p.title,
        title_ru=p.title_ru,
        description=p.description,
        tags=json.loads(p.tags),
        collection_line=p.collection_line,
        collection_line_ru=p.collection_line_ru,
        status=p.status,
        scheduled_at=p.scheduled_at,
        posted_at=p.posted_at,
        external_post_id=p.external_post_id,
        error_message=p.error_message,
        created_at=p.created_at,
        image_ids=[pi.image_id for pi in ordered],
    )


def _image_urls(post: Post, base_url: str) -> list[str]:
    return [
        f"{base_url.rstrip('/')}/{pi.image.r2_key}"
        for pi in post.post_images
        if pi.image.deleted_at is None
    ]


def _build_caption(post: Post) -> str:
    tags = " ".join(json.loads(post.tags))
    if post.platform == "telegram":
        title = post.title_ru or post.title
        coll_line = post.collection_line_ru or post.collection_line
    else:
        title = post.title
        coll_line = post.collection_line
    parts = [part for part in [title, coll_line, post.description, tags] if part]
    return "\n\n".join(parts)


def _do_telegram(post: Post, settings) -> dict:
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Telegram | post=%s | %d images | caption: %s", post.id, len(urls), caption[:120]
        )
        return {"ok": True, "fake": True}
    svc = TelegramService(settings.telegram_bot_token, settings.telegram_channel_id)
    return svc.post_media_group(urls, caption)


def _do_instagram(post: Post, settings) -> dict:
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Instagram | post=%s | %d images | caption: %s",
            post.id,
            len(urls),
            caption[:120],
        )
        return {"ok": True, "fake": True}
    svc = InstagramService(settings.instagram_access_token, settings.instagram_user_id)
    return svc.post(urls, caption)


def _do_facebook(post: Post, settings) -> dict:
    if not settings.facebook_page_id:
        return {"ok": True, "skipped": True}
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Facebook | post=%s | %d images | caption: %s", post.id, len(urls), caption[:120]
        )
        return {"ok": True, "fake": True}
    svc = FacebookService(settings.facebook_page_access_token, settings.facebook_page_id)
    return svc.post(urls, caption)


def execute_post(post: Post, db: Session, settings) -> PostResult:
    if post.status == "posted" or post.external_post_id:
        return PostResult(success=False, message="Already posted (duplicate protection)")

    if post.platform == "telegram":
        result = _do_telegram(post, settings)
        external_id = None
    elif post.platform == "instagram":
        result = _do_instagram(post, settings)
        external_id = result.get("media_id")
    elif post.platform == "facebook":
        result = _do_facebook(post, settings)
        external_id = result.get("post_id")
    else:
        return PostResult(success=False, message=f"Unknown platform: {post.platform}")

    if result.get("ok"):
        post.status = "posted"
        post.posted_at = datetime.now(UTC)
        post.external_post_id = external_id
        post.error_message = ""
        db.commit()
        prefix = "[FAKE] " if result.get("fake") else ""
        return PostResult(success=True, message=f"{prefix}Posted to {post.platform}")

    msg = result.get("description", "Unknown error")
    post.status = "failed"
    post.error_message = msg
    db.commit()
    return PostResult(success=False, message=msg)


def _compute_collection_line(series: Series, lang: str = "en") -> str | None:
    coll = series.collection
    if not coll or coll.deleted_at is not None:
        return None
    num = (series.collection_number or "").strip()
    name = (coll.name_ru or coll.name) if lang == "ru" else coll.name
    return f"◈ {name} #{num}" if num else f"◈ {name}"


def _create_post_images(post: Post, image_ids: list[str], db: Session) -> None:
    for idx, img_id in enumerate(image_ids):
        db.add(PostImage(post_id=post.id, image_id=img_id, order_index=idx))


@router.get("/api/series/{series_id}/posts")
def list_posts(series_id: str, db: Session = Depends(get_db)) -> list[PostResponse]:
    s = db.get(Series, series_id)
    if not s or s.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Series not found")
    posts = db.scalars(
        select(Post)
        .where(Post.series_id == series_id, Post.deleted_at.is_(None))
        .order_by(Post.created_at)
    ).all()
    return [post_to_resp(p) for p in posts]


@router.post("/api/series/{series_id}/posts")
def create_posts(
    series_id: str, body: PostBatchCreate, db: Session = Depends(get_db)
) -> list[PostResponse]:
    s = db.get(Series, series_id)
    if not s or s.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Series not found")

    invalid = set(body.platforms) - VALID_PLATFORMS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid platforms: {invalid}")

    # Validate image IDs belong to this series
    valid_ids = {img.id for img in s.images if img.deleted_at is None}
    bad = set(body.image_ids) - valid_ids
    if bad:
        raise HTTPException(status_code=400, detail=f"Images not in series: {bad}")

    created = []
    for platform in body.platforms:
        if platform == "telegram":
            description = body.description_telegram
            tags = json.dumps(body.tags_telegram)
        else:
            description = body.description_other
            tags = json.dumps(body.tags_other)

        p = Post(
            series_id=series_id,
            platform=platform,
            title=body.title,
            title_ru=body.title_ru,
            description=description,
            tags=tags,
            collection_line=body.collection_line
            if body.collection_line is not None
            else _compute_collection_line(s, lang="en"),
            collection_line_ru=body.collection_line_ru
            if body.collection_line_ru is not None
            else _compute_collection_line(s, lang="ru"),
            status="draft",
            scheduled_at=body.scheduled_at.replace(tzinfo=None) if body.scheduled_at else None,
            created_at=datetime.now(UTC),
        )
        if body.scheduled_at:
            p.status = "scheduled"
        db.add(p)
        db.flush()
        _create_post_images(p, body.image_ids, db)
        db.flush()
        created.append(p)

    db.commit()
    for p in created:
        db.refresh(p)
    return [post_to_resp(p) for p in created]


@router.get("/api/posts/{post_id}")
def get_post(post_id: str, db: Session = Depends(get_db)) -> PostResponse:
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post_to_resp(p)


@router.patch("/api/posts/{post_id}")
def update_post(post_id: str, body: PostUpdate, db: Session = Depends(get_db)) -> PostResponse:
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.status == "posted":
        raise HTTPException(status_code=400, detail="Cannot edit a posted post")

    if body.title is not None:
        p.title = body.title
    if body.title_ru is not None:
        p.title_ru = body.title_ru
    if body.description is not None:
        p.description = body.description
    if body.tags is not None:
        p.tags = json.dumps(body.tags)
    if "collection_line" in body.model_fields_set:
        p.collection_line = body.collection_line
    if "collection_line_ru" in body.model_fields_set:
        p.collection_line_ru = body.collection_line_ru
    if body.image_ids is not None:
        # Validate image IDs belong to the series
        series = db.get(Series, p.series_id)
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")
        valid_ids = {img.id for img in series.images if img.deleted_at is None}
        bad = set(body.image_ids) - valid_ids
        if bad:
            raise HTTPException(status_code=400, detail=f"Images not in series: {bad}")
        # Replace PostImages
        for pi in list(p.post_images):
            db.delete(pi)
        db.flush()
        _create_post_images(p, body.image_ids, db)

    db.commit()
    db.refresh(p)
    return post_to_resp(p)


@router.delete("/api/posts/{post_id}")
def delete_post(post_id: str, db: Session = Depends(get_db)):
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.status == "posted":
        raise HTTPException(status_code=400, detail="Cannot delete a posted post")
    p.deleted_at = datetime.now(UTC)
    db.commit()
    return {"deleted": post_id}


@router.post("/api/posts/{post_id}/post")
def post_now(post_id: str, db: Session = Depends(get_db)) -> PostResult:
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.status == "posted":
        return PostResult(success=False, message="Already posted")
    if not p.post_images:
        raise HTTPException(status_code=400, detail="No images in post")
    settings = get_or_create_settings(db)
    return execute_post(p, db, settings)


@router.post("/api/posts/{post_id}/schedule")
def schedule_post(
    post_id: str, body: PostScheduleRequest, db: Session = Depends(get_db)
) -> PostResponse:
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.status == "posted":
        raise HTTPException(status_code=400, detail="Cannot reschedule a posted post")
    p.scheduled_at = body.datetime_utc.replace(tzinfo=None)
    p.status = "scheduled"
    db.commit()
    return post_to_resp(p)


@router.delete("/api/posts/{post_id}/schedule")
def cancel_post_schedule(post_id: str, db: Session = Depends(get_db)) -> PostResponse:
    p = db.get(Post, post_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.status != "scheduled":
        raise HTTPException(status_code=400, detail="Post is not scheduled")
    p.scheduled_at = None
    p.status = "draft"
    db.commit()
    return post_to_resp(p)
