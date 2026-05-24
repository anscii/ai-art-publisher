import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_config
from app.database import get_db
from app.models import Post, PostImage
from app.routers.settings import get_or_create_settings
from app.scheduler import run_scheduled_posts
from app.schemas import QueueItem
from app.services.storage import get_public_base_url

router = APIRouter(tags=["scheduling"])


@router.post("/internal/run-scheduler", include_in_schema=False)
def trigger_scheduler(request: Request, db: Session = Depends(get_db)):
    cfg = get_config()
    token = request.headers.get("X-Scheduler-Token", "")
    if not cfg.scheduler_secret or not secrets.compare_digest(token, cfg.scheduler_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_scheduled_posts()
    return {"status": "ok"}


@router.get("/api/queue")
def get_queue(db: Session = Depends(get_db)) -> list[QueueItem]:
    settings = get_or_create_settings(db)
    base_url = get_public_base_url(settings)
    posts = db.scalars(
        select(Post)
        .options(
            selectinload(Post.series),
            selectinload(Post.post_images).selectinload(PostImage.image),
        )
        .where(Post.status == "scheduled", Post.deleted_at.is_(None))
        .order_by(Post.scheduled_at)
    ).all()
    items = []
    for p in posts:
        if p.scheduled_at is None:
            continue
        cover_url = None
        if p.post_images and base_url:
            first = min(p.post_images, key=lambda pi: pi.order_index)
            if first.image:
                cover_url = f"{base_url}/{first.image.r2_key}"
        items.append(
            QueueItem(
                post_id=p.id,
                series_id=p.series_id,
                series_name=(p.series.name or p.series.title or p.series.original_folder_name or "")
                if p.series
                else "",
                platform=p.platform,
                title=p.title,
                scheduled_at=p.scheduled_at,
                cover_url=cover_url,
            )
        )
    return items
