import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.models import Series
from app.routers.settings import get_or_create_settings
from app.schemas import PostResult
from app.services.facebook import FacebookService
from app.services.instagram import InstagramService
from app.services.telegram import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/series", tags=["posting"])


def _build_tg_caption(s: Series) -> str:
    tags = " ".join(json.loads(s.tags_telegram))
    return f"{s.description_ru}\n\n{tags}".strip()


def _build_ig_caption(s: Series) -> str:
    tags = " ".join(json.loads(s.tags_instagram))
    parts = [p for p in [s.title, s.description_en, tags] if p]
    return "\n\n".join(parts)


def _image_urls(s: Series, base_url: str) -> list[str]:
    imgs = sorted(
        [i for i in s.images if i.status == "queued" and i.deleted_at is None],
        key=lambda i: i.order_index,
    )
    return [f"{base_url.rstrip('/')}/{img.r2_key}" for img in imgs]


def _after_post_success(s: Series) -> None:
    for img in s.images:
        if img.status == "queued":
            img.status = "posted"
    non_skip = [i for i in s.images if i.status != "skip"]
    s.status = "posted" if all(i.status == "posted" for i in non_skip) else "partial_posted"


def _do_telegram(s: Series, settings) -> dict:
    urls = _image_urls(s, settings.r2_public_base_url)
    caption = _build_tg_caption(s)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Telegram | series=%s | %d images | caption: %s", s.id, len(urls), caption[:120]
        )
        return {"ok": True, "fake": True}
    svc = TelegramService(settings.telegram_bot_token, settings.telegram_channel_id)
    return svc.post_media_group(urls, caption)


def _do_instagram(s: Series, settings) -> dict:
    urls = _image_urls(s, settings.r2_public_base_url)
    caption = _build_ig_caption(s)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Instagram | series=%s | %d images | caption: %s", s.id, len(urls), caption[:120]
        )
        return {"ok": True, "fake": True}
    svc = InstagramService(settings.instagram_access_token, settings.instagram_user_id)
    return svc.post(urls, caption)


def _do_facebook(s: Series, settings) -> dict:
    if not settings.facebook_page_id:
        return {"ok": True, "skipped": True}
    urls = _image_urls(s, settings.r2_public_base_url)
    caption = _build_ig_caption(s)
    if get_config().fake_posting:
        logger.info(
            "[FAKE] Facebook | series=%s | %d images | caption: %s", s.id, len(urls), caption[:120]
        )
        return {"ok": True, "fake": True}
    svc = FacebookService(settings.facebook_page_access_token, settings.facebook_page_id)
    return svc.post(urls, caption)


def _handle_result(
    db: Session, s: Series, result: dict, platform: str, facebook_result: dict | None = None
) -> PostResult:
    if result["ok"]:
        if platform in ("telegram", "both"):
            s.posted_to_telegram_at = datetime.utcnow()
        if platform in ("instagram", "both"):
            s.posted_to_instagram_at = datetime.utcnow()
            if facebook_result and facebook_result.get("ok") and not facebook_result.get("skipped"):
                s.posted_to_facebook_at = datetime.utcnow()
        _after_post_success(s)
        db.commit()
        message = f"Posted to {platform}"
        if facebook_result and facebook_result.get("ok") and not facebook_result.get("skipped"):
            message += " and FB Page"
        if result.get("fake"):
            message = f"[FAKE] {message}"
        return PostResult(success=True, message=message)
    msg = result.get("description", "Unknown error")
    s.notes = (s.notes + f"\n[{platform} error] {msg}").strip()
    db.commit()
    return PostResult(success=False, message=msg)


def _check_queued(s: Series) -> None:
    if not any(i.status == "queued" for i in s.images):
        raise HTTPException(status_code=400, detail="No images queued for posting")


@router.post("/{series_id}/post/telegram")
def post_telegram(series_id: str, db: Session = Depends(get_db)) -> PostResult:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    _check_queued(s)
    settings = get_or_create_settings(db)
    return _handle_result(db, s, _do_telegram(s, settings), "telegram")


@router.post("/{series_id}/post/instagram")
def post_instagram(series_id: str, db: Session = Depends(get_db)) -> PostResult:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    _check_queued(s)
    settings = get_or_create_settings(db)
    ig = _do_instagram(s, settings)
    fb = _do_facebook(s, settings)
    return _handle_result(db, s, ig, "instagram", fb)


@router.post("/{series_id}/post/both")
def post_both(series_id: str, db: Session = Depends(get_db)) -> PostResult:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    _check_queued(s)
    settings = get_or_create_settings(db)
    tg = _do_telegram(s, settings)
    ig = _do_instagram(s, settings)
    fb = _do_facebook(s, settings)
    if tg["ok"] and ig["ok"]:
        s.posted_to_telegram_at = datetime.utcnow()
        s.posted_to_instagram_at = datetime.utcnow()
        if fb.get("ok") and not fb.get("skipped"):
            s.posted_to_facebook_at = datetime.utcnow()
        _after_post_success(s)
        db.commit()
        prefix = "[FAKE] " if tg.get("fake") or ig.get("fake") else ""
        return PostResult(success=True, message=f"{prefix}Posted to both")
    errors = []
    if not tg["ok"]:
        errors.append(f"Telegram: {tg.get('description')}")
    if not ig["ok"]:
        errors.append(f"Instagram: {ig.get('description')}")
    s.notes = (s.notes + "\n" + "; ".join(errors)).strip()
    db.commit()
    return PostResult(success=False, message="; ".join(errors))
