import json
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def run_scheduled_posts():
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import Series
    from app.routers.posting import _after_post_success, _do_facebook, _do_instagram, _do_telegram
    from app.routers.settings import get_or_create_settings

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = db.scalars(
            select(Series)
            .where(Series.status == "scheduled")
            .where(Series.scheduled_at <= now)
            .order_by(Series.scheduled_at)
            .limit(5)
        ).all()

        logger.info(f"Found {len(due)} scheduled posts")

        settings = get_or_create_settings(db)
        for s in due:
            targets = json.loads(s.scheduled_targets)
            try:
                if "telegram" in targets:
                    result = _do_telegram(s, settings)
                    if result["ok"]:
                        s.posted_to_telegram_at = datetime.utcnow()
                    else:
                        raise RuntimeError(result.get("description", "TG error"))
                if "instagram" in targets:
                    result = _do_instagram(s, settings)
                    if result["ok"]:
                        s.posted_to_instagram_at = datetime.utcnow()
                        fb = _do_facebook(s, settings)
                        if fb.get("ok") and not fb.get("skipped"):
                            s.posted_to_facebook_at = datetime.utcnow()
                    else:
                        raise RuntimeError(result.get("description", "IG error"))
                _after_post_success(s)
                from app.config import get_config

                prefix = "[FAKE] " if get_config().fake_posting else ""
                logger.info("%sScheduled post success: %s", prefix, s.id)
            except Exception as e:
                s.status = "approved"
                s.notes = (s.notes + f"\n[scheduler error] {e}").strip()
                logger.error("Scheduled post failed for %s: %s", s.id, e)
            db.commit()
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        run_scheduled_posts,
        "interval",
        minutes=30,
        id="scheduled_posts",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
