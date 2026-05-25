"""Public API endpoints for the landing page."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.enums import Platform
from app.models import Post, PostImage
from app.routers.settings import get_or_create_settings
from app.services.storage import get_public_base_url

router = APIRouter(prefix="/api/landing", tags=["landing"])


class RecentPostCard(BaseModel):
    id: str
    platform: str
    title: str
    description: str | None
    posted_at: datetime
    thumbnail_url: str | None
    post_url: str | None


class LandingRecentResponse(BaseModel):
    posts: list[RecentPostCard]
    total_posted: int


@router.get("/recent", response_model=LandingRecentResponse)
def get_landing_recent(db: Session = Depends(get_db)) -> LandingRecentResponse:
    settings = get_or_create_settings(db)
    base_url = get_public_base_url(settings)

    recent = db.scalars(
        select(Post)
        .options(selectinload(Post.post_images).selectinload(PostImage.image))
        .where(
            Post.status == "posted",
            Post.deleted_at.is_(None),
            Post.posted_at.isnot(None),
            Post.platform == Platform.instagram,
        )
        .order_by(Post.posted_at.desc())
        .limit(4)
    ).all()

    total = (
        db.scalar(
            select(func.count(Post.id)).where(
                Post.status == "posted", Post.deleted_at.is_(None), Post.posted_at.isnot(None)
            )
        )
        or 0
    )

    cards: list[RecentPostCard] = []
    for p in recent:
        ordered = sorted(p.post_images, key=lambda pi: pi.order_index)
        thumb: str | None = None
        if ordered and ordered[0].image and ordered[0].image.deleted_at is None:
            thumb = f"{base_url}/{ordered[0].image.r2_key}" if base_url else None
        cards.append(
            RecentPostCard(
                id=p.id,
                platform=p.platform,
                title=p.title or p.title_ru or "",
                description=p.description or None,
                posted_at=p.posted_at,  # type: ignore[arg-type]
                thumbnail_url=thumb,
                post_url=p.post_url,
            )
        )

    return LandingRecentResponse(posts=cards, total_posted=total)
