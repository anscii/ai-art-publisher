from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image, Series
from app.routers.settings import get_or_create_settings
from app.schemas import TrashImage, TrashResponse, TrashSeries

router = APIRouter(prefix="/api/trash", tags=["trash"])


@router.get("")
def get_trash(db: Session = Depends(get_db)) -> TrashResponse:
    settings = get_or_create_settings(db)
    base_url = settings.r2_public_base_url.rstrip("/")

    del_series = db.scalars(
        select(Series).where(Series.deleted_at.isnot(None)).order_by(Series.deleted_at.desc())
    ).all()

    del_images = db.scalars(
        select(Image)
        .where(Image.deleted_at.isnot(None))
        .join(Series, Image.series_id == Series.id)
        .where(Series.deleted_at.is_(None))
        .order_by(Image.deleted_at.desc())
    ).all()

    return TrashResponse(
        series=[
            TrashSeries(
                id=s.id,
                title=s.title,
                original_folder_name=s.original_folder_name,
                deleted_at=s.deleted_at,  # type: ignore[arg-type]
                image_count=len(s.images),
                cover_url=f"{base_url}/{s.images[0].r2_key}" if s.images and base_url else None,
            )
            for s in del_series
        ],
        images=[
            TrashImage(
                id=i.id,
                series_id=i.series_id,
                series_title=i.series.title or i.series.original_folder_name or i.series_id[:8],
                original_filename=i.original_filename,
                public_url=f"{base_url}/{i.r2_key}" if base_url else i.r2_key,
                deleted_at=i.deleted_at,  # type: ignore[arg-type]
            )
            for i in del_images
        ],
    )


@router.post("/series/{series_id}/restore")
def restore_series(series_id: str, db: Session = Depends(get_db)):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    s.deleted_at = None
    db.commit()
    return {"restored": series_id}


@router.post("/images/{image_id}/restore")
def restore_image(image_id: str, db: Session = Depends(get_db)):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Not found")
    img.deleted_at = None
    db.commit()
    return {"restored": image_id}


@router.delete("/series/{series_id}")
def permanently_delete_series(series_id: str, db: Session = Depends(get_db)):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    settings = get_or_create_settings(db)
    try:
        from app.services.storage import get_storage_from_settings

        storage = get_storage_from_settings(settings)
        for img in s.images:
            storage.delete(img.r2_key)
    except Exception:
        pass
    db.delete(s)
    db.commit()
    return {"deleted": series_id}


@router.delete("/images/{image_id}")
def permanently_delete_image(image_id: str, db: Session = Depends(get_db)):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Not found")
    settings = get_or_create_settings(db)
    try:
        from app.services.storage import get_storage_from_settings

        get_storage_from_settings(settings).delete(img.r2_key)
    except Exception:
        pass
    db.delete(img)
    db.commit()
    return {"deleted": image_id}


@router.delete("")
def empty_trash(db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    del_series = db.scalars(select(Series).where(Series.deleted_at.isnot(None))).all()
    del_images = db.scalars(
        select(Image)
        .where(Image.deleted_at.isnot(None))
        .join(Series, Image.series_id == Series.id)
        .where(Series.deleted_at.is_(None))
    ).all()
    try:
        from app.services.storage import get_storage_from_settings

        storage = get_storage_from_settings(settings)
        for s in del_series:
            for img in s.images:
                storage.delete(img.r2_key)
        for img in del_images:
            storage.delete(img.r2_key)
    except Exception:
        pass
    for s in del_series:
        db.delete(s)
    for img in del_images:
        db.delete(img)
    db.commit()
    return {"emptied": True}
