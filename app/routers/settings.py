import json
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIVariant, AppSettings, Series
from app.schemas import AIProviderModelStat, AIStatsResponse, SettingsUpdate
from app.services.ai.catalogue import PROVIDER_MODELS

router = APIRouter(prefix="/api/settings", tags=["settings"])
stats_router = APIRouter(prefix="/api/stats", tags=["stats"])

_SECRET_FIELDS = {
    "anthropic_api_key",
    "openai_api_key",
    "google_api_key",
    "deepseek_api_key",
    "openrouter_api_key",
    "telegram_bot_token",
    "telegram_api_hash",
    "telegram_session_string",
    "instagram_access_token",
    "facebook_page_access_token",
    "pinterest_access_token",
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
def get_providers() -> dict:
    return PROVIDER_MODELS


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict:
    return _to_dict(get_or_create_settings(db))


@router.put("")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    s = get_or_create_settings(db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    db.commit()
    return _to_dict(s)


@router.post("/test/{service}")
def test_connection(service: str, db: Session = Depends(get_db)) -> dict:
    s = get_or_create_settings(db)
    handlers = {
        "telegram": lambda: _test_telegram(s.telegram_bot_token),
        "instagram": lambda: _test_instagram(s.instagram_access_token, s.instagram_user_id),
        "facebook_page": lambda: _test_facebook_page(
            s.facebook_page_access_token, s.facebook_page_id
        ),
        "pinterest": lambda: _test_pinterest(s.pinterest_access_token),
        "anthropic": lambda: _test_anthropic(s.anthropic_api_key),
        "openai": lambda: _test_openai(s.openai_api_key),
        "google": lambda: _test_google(s.google_api_key),
        "deepseek": lambda: _test_deepseek(s.deepseek_api_key),
        "openrouter": lambda: _test_openrouter(s.openrouter_api_key),
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
            model="claude-haiku-4-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return {"ok": True, "message": "Connected"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_openai_compatible(key: str, base_url: str | None = None) -> dict:
    if not key:
        return {"ok": False, "message": "API key not configured"}
    try:
        import openai

        if base_url:
            openai.OpenAI(api_key=key, base_url=base_url).models.list()
        else:
            openai.OpenAI(api_key=key).models.list()
        return {"ok": True, "message": "Connected"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _test_openai(key: str) -> dict:
    return _test_openai_compatible(key)


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


def _test_deepseek(key: str) -> dict:
    return _test_openai_compatible(key, base_url="https://api.deepseek.com")


def _test_openrouter(key: str) -> dict:
    return _test_openai_compatible(key, base_url="https://openrouter.ai/api/v1")


@stats_router.get("/ai", response_model=AIStatsResponse)
def get_ai_stats(
    db: Session = Depends(get_db),
    range: str = Query("all", pattern="^(all|week)$"),
):
    since: datetime | None = None
    if range == "week":
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)

    base_q = db.query(AIVariant)
    if since is not None:
        base_q = base_q.filter(AIVariant.generated_at >= since)

    generated = (
        base_q.with_entities(
            AIVariant.provider,
            AIVariant.model,
            func.count().label("count"),
            func.sum(AIVariant.cost_usd).label("total_cost"),
        )
        .group_by(AIVariant.provider, AIVariant.model)
        .order_by(func.count().desc())
        .all()
    )
    chosen_q = db.query(AIVariant.provider, AIVariant.model, func.count().label("count")).join(
        Series, Series.chosen_variant_id == AIVariant.id
    )
    if since is not None:
        chosen_q = chosen_q.filter(AIVariant.generated_at >= since)
    chosen_raw = chosen_q.group_by(AIVariant.provider, AIVariant.model).all()
    chosen_map: dict[tuple[str, str], int] = {
        (r.provider, r.model): cast(int, r.count) for r in chosen_raw
    }

    rows = []
    for provider, model, count, total_cost in generated:
        total_cost = total_cost or 0.0
        chosen = chosen_map.get((provider, model), 0)
        selection_rate = round(chosen / count * 100, 1) if count else 0.0
        cost_per_sel = round(total_cost / chosen, 6) if chosen else None
        rows.append(
            AIProviderModelStat(
                provider=provider,
                model=model,
                generated=count,
                chosen=chosen,
                total_cost_usd=round(total_cost, 6),
                selection_rate=selection_rate,
                cost_per_selection=cost_per_sel,
            )
        )

    return AIStatsResponse(
        rows=rows,
        total_generated=sum(r.generated for r in rows),
        total_chosen=sum(r.chosen for r in rows),
        total_cost_usd=round(sum(r.total_cost_usd for r in rows), 6),
    )


def _test_pinterest(token: str | None) -> dict:
    import httpx

    if not token:
        return {"ok": False, "message": "Access token not configured"}
    try:
        r = httpx.get(
            "https://api.pinterest.com/v5/boards",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 25},
            timeout=5,
        )
        d = r.json()
        if "items" in d:
            names = [b["name"] for b in d["items"]]
            preview = ", ".join(names[:5]) or "(none)"
            return {"ok": True, "message": f"Connected — boards: {preview}"}
        return {"ok": False, "message": d.get("message", "Unknown error")}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.get("/pinterest/boards")
def get_pinterest_boards(db: Session = Depends(get_db)) -> dict:
    s = get_or_create_settings(db)
    try:
        board_map = json.loads(s.pinterest_board_map) if s.pinterest_board_map else {}
    except (json.JSONDecodeError, TypeError):
        board_map = {}
    return {"boards": list(board_map.keys())}


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
