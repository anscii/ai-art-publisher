from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Post
from app.schemas import QueueItem

router = APIRouter(tags=["scheduling"])


@router.get("/api/queue")
def get_queue(db: Session = Depends(get_db)) -> list[QueueItem]:
    posts = db.scalars(
        select(Post)
        .options(selectinload(Post.series))
        .where(Post.status == "scheduled", Post.deleted_at.is_(None))
        .order_by(Post.scheduled_at)
    ).all()
    return [
        QueueItem(
            post_id=p.id,
            series_id=p.series_id,
            series_name=(p.series.name or p.series.title or p.series.original_folder_name or "")
            if p.series
            else "",
            platform=p.platform,
            title=p.title,
            scheduled_at=p.scheduled_at,
        )
        for p in posts
        if p.scheduled_at is not None
    ]
