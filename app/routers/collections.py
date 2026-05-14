from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collection, Series
from app.schemas import CollectionCreate, CollectionResponse, CollectionUpdate

router = APIRouter(prefix="/api/collections", tags=["collections"])


def _build_counts(db: Session) -> dict[str, tuple[int, dict[str, int]]]:
    rows = db.execute(
        select(Series.collection_id, Series.status, func.count().label("cnt"))
        .where(Series.deleted_at.is_(None), Series.collection_id.isnot(None))
        .group_by(Series.collection_id, Series.status)
    ).all()
    totals: dict[str, int] = defaultdict(int)
    by_status: dict[str, dict[str, int]] = defaultdict(dict)
    for cid, status, cnt in rows:
        totals[cid] += cnt
        by_status[cid][status] = cnt
    return {cid: (totals[cid], by_status[cid]) for cid in totals}


def collection_to_resp(c: Collection, counts: dict | None = None) -> CollectionResponse:
    total, by_status = (counts or {}).get(c.id, (0, {}))
    return CollectionResponse(
        id=c.id,
        name=c.name,
        name_ru=c.name_ru,
        created_at=c.created_at,
        series_total=total,
        series_by_status=by_status,
    )


@router.get("")
def list_collections(db: Session = Depends(get_db)) -> list[CollectionResponse]:
    rows = db.scalars(
        select(Collection).where(Collection.deleted_at.is_(None)).order_by(Collection.name)
    ).all()
    counts = _build_counts(db)
    return [collection_to_resp(c, counts) for c in rows]


@router.post("")
def create_collection(body: CollectionCreate, db: Session = Depends(get_db)) -> CollectionResponse:
    c = Collection(name=body.name, name_ru=body.name_ru, created_at=datetime.now(UTC))
    db.add(c)
    db.commit()
    db.refresh(c)
    return collection_to_resp(c)


@router.patch("/{collection_id}")
def update_collection(
    collection_id: str, body: CollectionUpdate, db: Session = Depends(get_db)
) -> CollectionResponse:
    c = db.get(Collection, collection_id)
    if not c or c.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Collection not found")
    c.name = body.name
    c.name_ru = body.name_ru
    db.commit()
    return collection_to_resp(c)


@router.delete("/{collection_id}")
def delete_collection(collection_id: str, db: Session = Depends(get_db)):
    c = db.get(Collection, collection_id)
    if not c or c.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Collection not found")
    c.deleted_at = datetime.now(UTC)
    members = db.scalars(select(Series).where(Series.collection_id == collection_id)).all()
    for s in members:
        s.collection_id = None
        s.collection_index = None
        s.collection_number = None
    db.commit()
    return {"deleted": collection_id}
