"""Who pays for an AI call: the User's own key or the instance's Default AI Access (with Quota)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import DateTime, func, insert, literal, select
from sqlalchemy.orm import Session

from app.config import get_config
from app.models import AIRequest, AppSettings, UserSettings
from app.services.ai.catalogue import PROVIDER_LABEL, is_free_model


@dataclass
class AIAccess:
    api_key: str
    via_default: bool


def _today_start() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)


def own_key(us: UserSettings, provider: str) -> str:
    return {
        "anthropic": us.anthropic_api_key,
        "openai": us.openai_api_key,
        "google": us.google_api_key,
        "deepseek": us.deepseek_api_key,
        "openrouter": us.openrouter_api_key,
    }.get(provider, "")


def default_ai_enabled(settings: AppSettings) -> bool:
    return bool(settings.default_ai_openrouter_key) and settings.default_ai_daily_limit > 0


def used_today(user_id: str, db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(AIRequest)
            .where(
                AIRequest.user_id == user_id,
                AIRequest.via_default_access.is_(True),
                AIRequest.created_at >= _today_start(),
            )
        )
        or 0
    )


def resolve_ai_access(
    us: UserSettings, settings: AppSettings, provider: str, model: str
) -> AIAccess:
    """Pick the key for this call, or raise the 400 the User should see. No Quota check here."""
    own = own_key(us, provider)
    if own:
        return AIAccess(own, via_default=False)
    enabled = default_ai_enabled(settings)
    if provider == "openrouter" and enabled:
        if not is_free_model(model):
            raise HTTPException(
                400,
                "Free access covers free models only. "
                "Pick a :free model or add your own OpenRouter key.",
            )
        return AIAccess(settings.default_ai_openrouter_key, via_default=True)
    if get_config().fake_ai:
        return AIAccess("", via_default=False)
    label = PROVIDER_LABEL.get(provider, provider)
    hint = " or switch to OpenRouter free models" if enabled and provider != "openrouter" else ""
    raise HTTPException(400, f"No {label} key. Add one in Settings{hint}.")


def record_request(
    db: Session,
    *,
    user_id: str,
    kind: str,
    provider: str,
    model: str,
    via_default: bool,
    limit: int,
) -> str:
    """Insert the AI Request row; via_default rows only while today's count < limit (429 else).

    Returns the row id. Caller commits.
    """
    rid = str(uuid.uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    if not via_default:
        db.add(
            AIRequest(
                id=rid, user_id=user_id, kind=kind, provider=provider, model=model, created_at=now
            )
        )
        return rid
    # One conditional INSERT…SELECT so parallel requests can't both pass the count check.
    # Atomic only as the FIRST write of the transaction (autoflush=False): SQLite then retries
    # on BUSY with a fresh snapshot. Do not flush/write before this.
    count = (
        select(func.count())
        .select_from(AIRequest)
        .where(
            AIRequest.user_id == user_id,
            AIRequest.via_default_access.is_(True),
            AIRequest.created_at >= _today_start(),
        )
        .scalar_subquery()
    )
    stmt = insert(AIRequest).from_select(
        [
            "id",
            "user_id",
            "kind",
            "provider",
            "model",
            "via_default_access",
            "cost_usd",
            "created_at",
        ],
        select(
            literal(rid),
            literal(user_id),
            literal(kind),
            literal(provider),
            literal(model),
            literal(True),
            literal(0.0),
            literal(now, DateTime),
        ).where(count < limit),
    )
    if db.execute(stmt).rowcount == 0:
        raise HTTPException(
            429,
            f"Daily free limit reached ({limit}/day). "
            "Resets at 00:00 UTC, or add your own key in Settings.",
        )
    return rid
