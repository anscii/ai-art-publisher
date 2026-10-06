from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collection, Series, User
from app.ownership import get_owned
from app.routers.auth import get_current_user
from app.schemas import CollectionCreate, CollectionResponse, CollectionUpdate

router = APIRouter(prefix="/api/collections", tags=["collections"])


def _build_counts(db: Session, user: User) -> dict[str, tuple[int, dict[str, int]]]:
    rows = db.execute(
        select(Series.collection_id, Series.status, func.count().label("cnt"))
        .where(
            Series.user_id == user.id,
            Series.deleted_at.is_(None),
            Series.collection_id.isnot(None),
        )
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
def list_collections(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[CollectionResponse]:
    rows = db.scalars(
        select(Collection)
        .where(Collection.user_id == user.id, Collection.deleted_at.is_(None))
        .order_by(Collection.name)
    ).all()
    counts = _build_counts(db, user)
    return [collection_to_resp(c, counts) for c in rows]


@router.post("")
def create_collection(
    body: CollectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionResponse:
    c = Collection(
        user_id=user.id, name=body.name, name_ru=body.name_ru, created_at=datetime.now(UTC)
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return collection_to_resp(c)


@router.patch("/{collection_id}")
def update_collection(
    collection_id: str,
    body: CollectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionResponse:
    c = get_owned(Collection, collection_id, user, db)
    c.name = body.name
    c.name_ru = body.name_ru
    db.commit()
    return collection_to_resp(c)


@router.delete("/{collection_id}")
def delete_collection(
    collection_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    c = get_owned(Collection, collection_id, user, db)
    c.deleted_at = datetime.now(UTC)
    members = db.scalars(select(Series).where(Series.collection_id == collection_id)).all()
    for s in members:
        s.collection_id = None
        s.collection_index = None
        s.collection_number = None
    db.commit()
    return {"deleted": collection_id}
