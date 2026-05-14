import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def run_scheduled_posts():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.database import SessionLocal
    from app.models import Post, PostImage
    from app.routers.posts import execute_post
    from app.routers.settings import get_or_create_settings

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        due = db.scalars(
            select(Post)
            .options(selectinload(Post.post_images).selectinload(PostImage.image))
            .where(Post.status == "scheduled", Post.deleted_at.is_(None))
            .where(Post.scheduled_at <= now)
            .order_by(Post.scheduled_at)
            .limit(10)
        ).all()

        logger.info("Found %d scheduled posts due", len(due))

        settings = get_or_create_settings(db)
        for post in due:
            try:
                result = execute_post(post, db, settings)
                prefix = "[FAKE] " if not result.success and "FAKE" in result.message else ""
                if result.success:
                    logger.info(
                        "%sScheduled post success: %s platform=%s", prefix, post.id, post.platform
                    )
                else:
                    logger.error(
                        "Scheduled post failed: %s platform=%s msg=%s",
                        post.id,
                        post.platform,
                        result.message,
                    )
            except Exception as e:
                post.status = "failed"
                post.error_message = str(e)
                db.commit()
                logger.error(
                    "Scheduled post exception: %s platform=%s: %s", post.id, post.platform, e
                )
    finally:
        db.close()
