import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.models import AIVariant, Post, PostImage, Series
from app.routers.settings import get_or_create_settings
from app.schemas import PostBatchCreate, PostResponse, PostResult, PostScheduleRequest, PostUpdate
from app.services.facebook import FacebookService
from app.services.instagram import InstagramService
from app.services.pinterest import PinterestService
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["posts"])

VALID_PLATFORMS = {"telegram", "instagram", "facebook", "pinterest"}


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
        seo=p.seo,
        variant_id=p.variant_id,
        post_url=p.post_url,
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
        parts = [title, coll_line, post.description, tags]
    else:
        title = post.title
        coll_line = post.collection_line
        archive_footer = f"—\nFiled under:\n{post.seo}" if post.seo else None
        parts = [title, coll_line, post.description, archive_footer, tags]
    return "\n\n".join(p for p in parts if p)


def _response_fake_posting(
    post: Post, images_num: int, caption: str, platform: str | None = None
) -> dict:
    if not platform:
        platform = post.platform
    logger.info(
        "[FAKE] %s | post=%s | %d images | caption: \n%s",
        platform,
        post.id,
        images_num,
        caption,
    )
    return {"ok": True, "fake": True}


def _do_telegram(post: Post, settings) -> dict:
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        return _response_fake_posting(post=post, images_num=len(urls), caption=caption)
    svc = TelegramService(settings.telegram_bot_token, settings.telegram_channel_id)
    return svc.post_media_group(urls, caption)


def _do_instagram(post: Post, settings) -> dict:
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        return _response_fake_posting(post=post, images_num=len(urls), caption=caption)
    svc = InstagramService(settings.instagram_access_token, settings.instagram_user_id)
    return svc.post(urls, caption)


def _do_facebook(post: Post, settings) -> dict:
    if not settings.facebook_page_id:
        return {"ok": True, "skipped": True}
    urls = _image_urls(post, settings.r2_public_base_url)
    caption = _build_caption(post)
    if get_config().fake_posting:
        return _response_fake_posting(
            post=post, images_num=len(urls), caption=caption, platform="facebook"
        )
    svc = FacebookService(settings.facebook_page_access_token, settings.facebook_page_id)
    return svc.post(urls, caption)


def _do_pinterest(post: Post, settings, db: Session) -> dict:
    if not settings.pinterest_access_token:
        return {"ok": True, "skipped": True}
    urls = _image_urls(post, settings.r2_public_base_url)
    variant = None
    if post.series and post.series.chosen_variant_id:
        variant = next(
            (v for v in post.series.ai_variants if v.id == post.series.chosen_variant_id),
            None,
        )
    title = (variant.pinterest_title if variant else None) or post.title or ""
    description = (variant.pinterest_description if variant else None) or post.description or ""
    board_name = (variant.pinterest_board if variant else None) or ""
    try:
        board_map = json.loads(settings.pinterest_board_map) if settings.pinterest_board_map else {}
    except (json.JSONDecodeError, TypeError):
        board_map = {}
    if get_config().fake_posting:
        return _response_fake_posting(post=post, images_num=len(urls), caption=title)
    svc = PinterestService(settings.pinterest_access_token)
    board_id = board_map.get(board_name, "") or ""
    if not board_id and board_name:
        create_result = svc.create_board(board_name)
        if not create_result.get("ok"):
            return create_result
        board_id = create_result["board_id"]
        new_map = {**board_map, board_name: board_id}
        settings.pinterest_board_map = json.dumps(new_map)
        # Commit board_map before posting — if post_pins fails the board still
        # exists in Pinterest so the next attempt will find it in the map.
        db.commit()
    if not board_id:
        board_id = settings.pinterest_default_board_id or ""
    if not board_id:
        return {
            "ok": False,
            "description": "No board resolved — add a Default Board ID in Settings or ensure the chosen variant has a Pinterest board name",
        }
    return svc.post_pins(board_id, urls, title, description)


def _auto_mark_images_posted(series: Series, db: Session) -> None:
    """Mark images as posted when they appear in both a posted Telegram and a posted visual post."""
    telegram_ids: set[str] = set()
    visual_ids: set[str] = set()
    for p in series.posts:
        if p.status != "posted" or p.deleted_at is not None:
            continue
        ids = {pi.image_id for pi in p.post_images}
        if p.platform == "telegram":
            telegram_ids.update(ids)
        elif p.platform in ("instagram", "pinterest"):
            visual_ids.update(ids)
    both = telegram_ids & visual_ids
    if not both:
        return
    for img in series.images:
        if img.id in both and img.deleted_at is None and img.status not in ("skip", "posted"):
            img.status = "posted"


def _maybe_mark_series_posted(series: Series, db: Session) -> None:
    """Mark series as posted if all non-skip, non-deleted images are posted."""
    if series.status == "skip":
        return
    active = [img for img in series.images if img.deleted_at is None and img.status != "skip"]
    if active and all(img.status == "posted" for img in active):
        series.status = "posted"


def execute_post(post: Post, db: Session, settings) -> PostResult:
    if post.status == "posted" or post.external_post_id:
        return PostResult(success=False, message="Already posted (duplicate protection)")

    platform = post.platform

    post_url_value: str | None = None
    if post.platform == "telegram":
        result = _do_telegram(post, settings)
        external_id = None
        _ch = (settings.telegram_channel_id or "").strip()
        _mid = result.get("message_id")
        if _mid is not None and _ch.startswith("@"):
            post_url_value = f"https://t.me/{_ch.lstrip('@')}/{_mid}"
    elif post.platform == "instagram":
        result = _do_instagram(post, settings)
        external_id = result.get("media_id")
        post_url_value = result.get("permalink")
        if result.get("ok"):
            try:
                fb_result = _do_facebook(post, settings)
                if fb_result.get("ok") and not fb_result.get("skipped"):
                    platform = f"{platform} & facebook"
                elif not fb_result.get("ok") and not fb_result.get("skipped"):
                    logger.warning(
                        "Facebook auto-post failed for %s: %s",
                        post.id,
                        fb_result.get("description"),
                    )
            except Exception as exc:
                logger.warning("Facebook auto-post exception for %s: %s", post.id, exc)
    elif post.platform == "facebook":
        result = _do_facebook(post, settings)
        external_id = result.get("post_id")
    elif post.platform == "pinterest":
        result = _do_pinterest(post, settings, db)
        external_id = ",".join(result.get("pin_ids") or []) or None
    else:
        return PostResult(success=False, message=f"Unknown platform: {post.platform}")

    if result.get("ok"):
        post.status = "posted"
        post.posted_at = datetime.now(UTC)
        post.external_post_id = external_id
        post.post_url = post_url_value
        post.error_message = ""
        db.commit()
        _auto_mark_images_posted(post.series, db)
        _maybe_mark_series_posted(post.series, db)
        db.commit()
        prefix = "[FAKE] " if result.get("fake") else ""
        return PostResult(success=True, message=f"{prefix}Posted to {platform}")

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
    return f"◈ {name} — {num}" if num else f"◈ {name}"


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


@router.post("/api/series/{series_id}/posts", status_code=201)
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

    chosen_variant = db.get(AIVariant, s.chosen_variant_id) if s.chosen_variant_id else None

    created = []
    for platform in body.platforms:
        if platform == "telegram":
            description = body.description_telegram
            tags = json.dumps(body.tags_telegram)
        else:
            description = body.description_other
            tags = json.dumps(body.tags_other)

        post_seo = (
            chosen_variant.instagram_seo if chosen_variant and platform != "telegram" else None
        )

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
            seo=post_seo,
            variant_id=s.chosen_variant_id,
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
def delete_post(post_id: str, db: Session = Depends(get_db)) -> dict:
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
