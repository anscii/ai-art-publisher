import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image, Series
from app.routers.settings import get_or_create_settings
from app.schemas import TrashImage, TrashResponse, TrashSeries
from app.services.storage import get_public_base_url, get_storage_from_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trash", tags=["trash"])


@router.get("")
def get_trash(db: Session = Depends(get_db)) -> TrashResponse:
    settings = get_or_create_settings(db)
    base_url = get_public_base_url(settings)

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
def restore_series(series_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    s.deleted_at = None
    db.commit()
    return {"restored": series_id}


@router.post("/images/{image_id}/restore")
def restore_image(image_id: str, db: Session = Depends(get_db)) -> dict:
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Not found")
    img.deleted_at = None
    db.commit()
    return {"restored": image_id}


@router.delete("/series/{series_id}")
def permanently_delete_series(series_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)
    for img in s.images:
        try:
            storage.delete(img.r2_key)
        except Exception as err:
            logger.error(
                "Storage delete failed for image %s (key %s) in series %s: %s",
                img.id,
                img.r2_key,
                series_id,
                err,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Storage delete failed for image {img.id}; series not removed",
            )
    db.delete(s)
    db.commit()
    return {"deleted": series_id}


@router.delete("/images/{image_id}")
def permanently_delete_image(image_id: str, db: Session = Depends(get_db)) -> dict:
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Not found")
    settings = get_or_create_settings(db)
    try:
        get_storage_from_settings(settings).delete(img.r2_key)
    except Exception as err:
        logger.error("Storage delete failed for image %s (key %s): %s", image_id, img.r2_key, err)
        raise HTTPException(status_code=500, detail="Storage delete failed; image not removed")
    db.delete(img)
    db.commit()
    return {"deleted": image_id}


@router.delete("")
def empty_trash(db: Session = Depends(get_db)) -> dict:
    settings = get_or_create_settings(db)
    del_series = db.scalars(select(Series).where(Series.deleted_at.isnot(None))).all()
    del_images = db.scalars(
        select(Image)
        .where(Image.deleted_at.isnot(None))
        .join(Series, Image.series_id == Series.id)
        .where(Series.deleted_at.is_(None))
    ).all()
    logger.info("Ready to delete %s series and %s images", len(del_series), len(del_images))
    storage = get_storage_from_settings(settings)

    series_to_delete = []
    for s in del_series:
        storage_ok = True
        for img in s.images:
            try:
                storage.delete(img.r2_key)
            except Exception as err:
                logger.error(
                    "Storage delete failed for image %s (key %s) in series %s: %s",
                    img.id,
                    img.r2_key,
                    s.id,
                    err,
                )
                storage_ok = False
                break
        if storage_ok:
            series_to_delete.append(s)

    images_to_delete = []
    for img in del_images:
        try:
            storage.delete(img.r2_key)
            images_to_delete.append(img)
        except Exception as err:
            logger.error("Storage delete failed for image %s (key %s): %s", img.id, img.r2_key, err)

    for s in series_to_delete:
        db.delete(s)
    for img in images_to_delete:
        db.delete(img)
    db.commit()
    return {"emptied": True}
