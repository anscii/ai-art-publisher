from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AIVariant, Image, Post, Series, Story, StoryFrame, User

# Join path from a model up to the model that carries user_id.
_PARENTS: dict[type, tuple[type, ...]] = {
    Image: (Series,),
    Post: (Series,),
    AIVariant: (Series,),
    Story: (Post, Series),
    StoryFrame: (Story, Post, Series),
}


def get_owned[T](
    model: type[T], obj_id: str, user: User, db: Session, *, include_deleted: bool = False
) -> T:
    """Load `model` row `obj_id` only if it belongs to `user`; 404 otherwise.

    Soft-deleted rows (the row itself or any parent on the path) count as
    missing unless include_deleted=True — only Trash routes pass that.
    """
    chain = (model, *_PARENTS.get(model, ()))
    q = db.query(model).filter(model.id == obj_id)  # type: ignore[attr-defined]
    for parent in chain[1:]:
        q = q.join(parent)
    q = q.filter(chain[-1].user_id == user.id)  # type: ignore[attr-defined]
    if not include_deleted:
        q = q.filter(*(m.deleted_at.is_(None) for m in chain if hasattr(m, "deleted_at")))
    obj = q.first()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
