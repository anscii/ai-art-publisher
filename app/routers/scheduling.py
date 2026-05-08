import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Series
from app.schemas import QueueItem, ScheduleRequest

router = APIRouter(tags=["scheduling"])


@router.post("/api/series/{series_id}/schedule")
def schedule_series(series_id: str, body: ScheduleRequest, db: Session = Depends(get_db)):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    s.scheduled_at = body.datetime_utc.replace(tzinfo=None)
    s.scheduled_targets = json.dumps(body.targets)
    s.status = "scheduled"
    db.commit()
    return {"scheduled_at": s.scheduled_at.isoformat(), "targets": body.targets}


@router.delete("/api/series/{series_id}/schedule")
def cancel_schedule(series_id: str, db: Session = Depends(get_db)):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    s.scheduled_at = None
    s.scheduled_targets = "[]"
    s.status = "approved"
    db.commit()
    return {"cancelled": series_id}


@router.get("/api/queue")
def get_queue(db: Session = Depends(get_db)) -> list[QueueItem]:
    rows = db.scalars(
        select(Series).where(Series.status == "scheduled").order_by(Series.scheduled_at)
    ).all()
    return [
        QueueItem(
            series_id=s.id,
            title=s.title or s.original_folder_name or "",
            original_folder_name=s.original_folder_name,
            scheduled_at=s.scheduled_at,
            targets=json.loads(s.scheduled_targets),
        )
        for s in rows
        if s.scheduled_at is not None
    ]
