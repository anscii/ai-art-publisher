from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSettings
from app.schemas import SettingsUpdate
from app.services.ai.catalogue import PROVIDER_MODELS

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SECRET_FIELDS = {
    "anthropic_api_key",
    "openai_api_key",
    "google_api_key",
    "telegram_bot_token",
    "instagram_access_token",
    "facebook_page_access_token",
    "r2_access_key",
    "r2_secret_key",
}


def get_or_create_settings(db: Session) -> AppSettings:
    s = db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _mask(field: str, value: str) -> str:
    return "****" if field in _SECRET_FIELDS and value else value


def _to_dict(s: AppSettings) -> dict:
    fields = [c.key for c in AppSettings.__table__.columns if c.key != "id"]
    return {f: _mask(f, getattr(s, f)) for f in fields}


@router.get("/providers")
def get_providers():
    return PROVIDER_MODELS


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return _to_dict(get_or_create_settings(db))


@router.put("")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    s = get_or_create_settings(db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    db.commit()
    return _to_dict(s)


@router.post("/test/{service}")
def test_connection(service: str, db: Session = Depends(get_db)):
    s = get_or_create_settings(db)
    handlers = {
        "telegram": lambda: _test_telegram(s.telegram_bot_token),
        "instagram": lambda: _test_instagram(s.instagram_access_token, s.instagram_user_id),
        "facebook_page": lambda: _test_facebook_page(
            s.facebook_page_access_token, s.facebook_page_id
        ),
        "anthropic": lambda: _test_anthropic(s.anthropic_api_key),
        "openai": lambda: _test_openai(s.openai_api_key),
        "google": lambda: _test_google(s.google_api_key),
        "r2": lambda: _test_r2(s),
    }
    if service not in handlers:
        raise HTTPException(status_code=404, detail="Unknown service")
    return handlers[service]()


def _test_telegram(token: str) -> dict:
    import httpx

    if not token:
        return {"ok": False, "message": "Token not configured"}
    try:
        r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        d = r.json()
        if d.get("ok"):
            return {"ok": True, "message": f"Connected as @{d['result']['username']}"}
        return {"ok": False, "message": d.get("description", "Unknown error")}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_instagram(token: str, user_id: str) -> dict:
    import httpx

    if not token or not user_id:
        return {"ok": False, "message": "Token or user ID not configured"}
    try:
        r = httpx.get(
            f"https://graph.instagram.com/v25.0/{user_id}",
            params={"fields": "id,username", "access_token": token},
            timeout=5,
        )
        d = r.json()
        if "id" in d:
            return {"ok": True, "message": f"Connected as {d.get('username', user_id)}"}
        return {"ok": False, "message": d.get("error", {}).get("message", "Unknown")}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_facebook_page(token: str, page_id: str) -> dict:
    import httpx

    if not token or not page_id:
        return {"ok": False, "message": "Token or page ID not configured"}
    try:
        r = httpx.get(
            f"https://graph.facebook.com/v25.0/{page_id}",
            params={"fields": "id,name", "access_token": token},
            timeout=5,
        )
        d = r.json()
        if "id" in d:
            return {"ok": True, "message": f"Connected to {d.get('name', page_id)}"}
        return {"ok": False, "message": d.get("error", {}).get("message", "Unknown")}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_anthropic(key: str) -> dict:
    if not key:
        return {"ok": False, "message": "API key not configured"}
    try:
        import anthropic

        anthropic.Anthropic(api_key=key).messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return {"ok": True, "message": "Connected"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_openai(key: str) -> dict:
    if not key:
        return {"ok": False, "message": "API key not configured"}
    try:
        import openai

        openai.OpenAI(api_key=key).models.list()
        return {"ok": True, "message": "Connected"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_google(key: str) -> dict:
    if not key:
        return {"ok": False, "message": "API key not configured"}
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
        list(genai.list_models())
        return {"ok": True, "message": "Connected"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_r2(s: AppSettings) -> dict:
    if not s.r2_endpoint or not s.r2_access_key:
        return {"ok": False, "message": "R2 not configured"}
    try:
        import boto3

        c = boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint,
            aws_access_key_id=s.r2_access_key,
            aws_secret_access_key=s.r2_secret_key,
            region_name="auto",
        )
        c.head_bucket(Bucket=s.r2_bucket)
        return {"ok": True, "message": f"Connected to bucket '{s.r2_bucket}'"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
