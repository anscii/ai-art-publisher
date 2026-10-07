from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSettings
from app.routers.auth import get_current_user
from app.routers.settings import (
    SECRET_FIELDS,
    _test_anthropic,
    _test_deepseek,
    _test_google,
    _test_openai,
    _test_openrouter,
    mask,
)
from app.schemas import UserSettingsUpdate
from app.services.ai.catalogue import IMAGE_EDIT_MODELS, PROVIDER_MODELS

router = APIRouter(tags=["user_settings"])

_TESTERS = {
    "anthropic": _test_anthropic,
    "openai": _test_openai,
    "google": _test_google,
    "deepseek": _test_deepseek,
    "openrouter": _test_openrouter,
}


def get_user_settings(user_id: str, db: Session) -> UserSettings:
    us = db.get(UserSettings, user_id)
    if not us:
        us = UserSettings(user_id=user_id)
        db.add(us)
        db.commit()
        db.refresh(us)
    return us


def _to_dict(us: UserSettings) -> dict:
    fields = [c.key for c in UserSettings.__table__.columns if c.key != "user_id"]
    return {f: mask(f, getattr(us, f)) for f in fields}


@router.get("/api/me/settings")
def get_my_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return _to_dict(get_user_settings(user.id, db))


@router.put("/api/me/settings")
def update_my_settings(
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    us = get_user_settings(user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        if field in SECRET_FIELDS and value == "****":
            continue  # masked placeholder echoed back, not a new value
        setattr(us, field, value)
    db.commit()
    return _to_dict(us)


@router.post("/api/me/settings/test/{provider}")
def test_my_provider(
    provider: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    if provider not in _TESTERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    return _TESTERS[provider](getattr(get_user_settings(user.id, db), f"{provider}_api_key"))


@router.get("/api/settings/providers")
def get_providers(user: User = Depends(get_current_user)) -> dict:
    return {**PROVIDER_MODELS, "image_edit": IMAGE_EDIT_MODELS}
