from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.config import AppConfig
from app.models import AIRequest, AppSettings, User, UserSettings
from app.services.ai.access import AIAccess, record_request, resolve_ai_access, used_today
from app.services.ai.catalogue import is_free_model

FREE = "google/gemma-4-31b-it:free"
FREE_ONLY = (
    "Free access covers free models only. Pick a :free model or add your own OpenRouter key."
)


def _settings(key="sk-inst", limit=20) -> AppSettings:
    return AppSettings(id=1, default_ai_openrouter_key=key, default_ai_daily_limit=limit)


def _us(**kw) -> UserSettings:
    return UserSettings(user_id="u", **kw)


def test_own_key_wins_even_for_paid_openrouter_model():
    a = resolve_ai_access(_us(openrouter_api_key="mine"), _settings(), "openrouter", "openai/gpt-6")
    assert a == AIAccess("mine", False)


def test_free_model_uses_instance_key():
    a = resolve_ai_access(_us(), _settings(), "openrouter", FREE)
    assert a == AIAccess("sk-inst", True)


def test_paid_model_without_own_key_rejected():
    with pytest.raises(HTTPException) as e:
        resolve_ai_access(_us(), _settings(), "openrouter", "openai/gpt-x")
    assert e.value.status_code == 400
    assert e.value.detail == FREE_ONLY


@pytest.mark.parametrize("s", [_settings(limit=0), _settings(key="")])
def test_default_access_off(s):
    with pytest.raises(HTTPException) as e:
        resolve_ai_access(_us(), s, "openrouter", FREE)
    assert e.value.detail == "No OpenRouter key. Add one in Settings."


def test_non_openrouter_hint_only_when_enabled():
    with pytest.raises(HTTPException) as e:
        resolve_ai_access(_us(), _settings(), "anthropic", "claude-haiku-4-5")
    assert "switch to OpenRouter free models" in e.value.detail
    with pytest.raises(HTTPException) as e:
        resolve_ai_access(_us(), _settings(limit=0), "anthropic", "claude-haiku-4-5")
    assert "switch to OpenRouter" not in e.value.detail
    assert e.value.detail == "No Anthropic key. Add one in Settings."


def test_fake_ai_keyless(monkeypatch):
    monkeypatch.setattr(AppConfig, "fake_ai", True)
    assert resolve_ai_access(_us(), _settings(key=""), "openrouter", FREE) == AIAccess("", False)
    with pytest.raises(HTTPException) as e:
        resolve_ai_access(_us(), _settings(), "openrouter", "openai/gpt-x")
    assert e.value.detail == FREE_ONLY


def _user(db, uid):
    db.add(User(id=uid, email=f"{uid}@x.com"))
    db.commit()


def _rec(db, uid, via=True, limit=20):
    rid = record_request(
        db,
        user_id=uid,
        kind="draft",
        provider="openrouter",
        model=FREE,
        via_default=via,
        limit=limit,
    )
    db.commit()
    return rid


def test_quota_20_then_429(db):
    _user(db, "a")
    for _ in range(20):
        _rec(db, "a")
    with pytest.raises(HTTPException) as e:
        _rec(db, "a")
    assert e.value.status_code == 429
    assert e.value.detail == (
        "Daily free limit reached (20/day). Resets at 00:00 UTC, or add your own key in Settings."
    )
    assert used_today("a", db) == 20


def test_own_key_rows_do_not_count(db):
    _user(db, "a")
    for _ in range(25):
        _rec(db, "a", via=False)
    _rec(db, "a", limit=1)
    assert used_today("a", db) == 1


def test_yesterday_and_other_users_do_not_count(db):
    _user(db, "a")
    _user(db, "b")
    for _ in range(3):
        _rec(db, "b", limit=3)
    old = _rec(db, "a", limit=1)
    row = db.get(AIRequest, old)
    row.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1, minutes=1)
    db.commit()
    assert used_today("a", db) == 0
    _rec(db, "a", limit=1)
    assert used_today("a", db) == 1


def test_is_free_model():
    assert is_free_model("openrouter/free")
    assert is_free_model("x/y:free")
    assert not is_free_model("x/y")
    assert not is_free_model("x:freeish")
