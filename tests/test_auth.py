import base64
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.config import AppConfig
from app.models import User
from app.routers.auth import (
    COOKIE_NAME,
    create_session_token,
    create_user_session_token,
    get_current_user,
    get_session_user_id,
    verify_session_token,
)

_SECRET = "test-secret-key"
_USER = "admin"
_PASS = "hunter2"


@pytest.fixture()
def auth_config(monkeypatch):
    monkeypatch.setattr(AppConfig, "auth_username", _USER)
    monkeypatch.setattr(AppConfig, "auth_password", _PASS)


# ── session token helpers ──────────────────────────────────────────────────────


def test_verify_valid_token():
    token = create_session_token(_SECRET, _USER)
    assert verify_session_token(token, _SECRET)


def test_verify_wrong_secret():
    token = create_session_token(_SECRET, _USER)
    assert not verify_session_token(token, "wrong-secret")


def test_verify_tampered_payload():
    token = create_session_token(_SECRET, _USER)
    payload, sig = token.rsplit(".", 1)
    tampered = base64.urlsafe_b64encode(b'{"u":"hacker","exp":9999999999}').decode()
    assert not verify_session_token(f"{tampered}.{sig}", _SECRET)


def test_verify_expired_token(monkeypatch):
    from app.routers import auth as auth_mod

    monkeypatch.setattr(auth_mod, "_MAX_AGE", -1)
    token = create_session_token(_SECRET, _USER)
    assert not verify_session_token(token, _SECRET)


def test_create_and_read_user_session_token():
    token = create_user_session_token(_SECRET, "user-abc-123")
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_session_user_id(request, _SECRET) == "user-abc-123"


def test_get_session_user_id_no_cookie():
    request = MagicMock()
    request.cookies = {}
    assert get_session_user_id(request, _SECRET) is None


def test_get_session_user_id_wrong_secret():
    token = create_user_session_token(_SECRET, "user-abc-123")
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_session_user_id(request, "wrong-secret") is None


def test_get_session_user_id_expired(monkeypatch):
    from app.routers import auth as auth_mod

    monkeypatch.setattr(auth_mod, "_MAX_AGE", -1)
    token = create_user_session_token(_SECRET, "user-abc-123")
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_session_user_id(request, _SECRET) is None


def test_get_session_user_id_ignores_legacy_username_token():
    """A legacy username-based token (payload key 'u') must not be misread as a user id."""
    token = create_session_token(_SECRET, "admin")
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_session_user_id(request, _SECRET) is None


# ── get_current_user ──────────────────────────────────────────────────────────


def test_get_current_user_via_session_cookie(db):
    u = User(email="friend@example.com", google_sub="g-1")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_user_session_token(_SECRET, u.id)
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    request.headers = {}
    result = get_current_user(request, db)
    assert result.id == u.id


def test_get_current_user_banned_rejected(db):
    from datetime import datetime

    u = User(email="banned@example.com", google_sub="g-2", banned_at=datetime.utcnow())
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_user_session_token(_SECRET, u.id)
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    request.headers = {}
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_no_session_rejected(db, monkeypatch):
    from app.config import AppConfig

    # Auth must be configured for the 401 path — otherwise the no-auth
    # fallback (below) kicks in.
    monkeypatch.setattr(AppConfig, "google_client_id", "client-id")
    request = MagicMock()
    request.cookies = {}
    request.headers = {}
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_no_auth_configured_returns_default_user(db):
    """reset_config blanks auth_username and google_client_id — dev/E2E mode."""
    request = MagicMock()
    request.cookies = {}
    request.headers = {}
    user = get_current_user(request, db)
    assert user.email == "local@localhost"
    # Second call resolves the same row, doesn't create a duplicate.
    assert get_current_user(request, db).id == user.id


def test_get_current_user_legacy_basic_auth_resolves_owner(db, auth_config, monkeypatch):
    from app.config import AppConfig

    monkeypatch.setattr(AppConfig, "owner_email", "owner@example.com")
    owner = User(email="owner@example.com", google_sub=None, is_admin=True)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    creds = base64.b64encode(f"{_USER}:{_PASS}".encode()).decode()
    request = MagicMock()
    request.cookies = {}
    request.headers = {"Authorization": f"Basic {creds}"}
    result = get_current_user(request, db)
    assert result.id == owner.id


# ── GET / routing ──────────────────────────────────────────────────────────────


def test_root_no_auth_configured_returns_app(client):
    """Auth disabled in tests by default — GET / returns the app HTML."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AI Art Publisher" in resp.text


def test_root_unauthenticated_returns_landing(client, auth_config):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    # Landing page has the AAP sign-in card, app HTML does not
    assert "aap-signin-card" in resp.text


def test_root_with_session_cookie_returns_app(client, auth_config):
    token = create_session_token(_SECRET, _USER)
    client.cookies.set(COOKIE_NAME, token)
    resp = client.get("/")
    client.cookies.clear()
    assert resp.status_code == 200
    assert "loginModal" not in resp.text


def test_root_with_basic_auth_header_returns_app(client, auth_config):
    creds = base64.b64encode(f"{_USER}:{_PASS}".encode()).decode()
    resp = client.get("/", headers={"Authorization": f"Basic {creds}"})
    assert resp.status_code == 200
    assert "loginModal" not in resp.text


# ── POST /auth/login ───────────────────────────────────────────────────────────


def test_login_correct_creds_sets_cookie(client, auth_config):
    resp = client.post(
        "/auth/login",
        data={"username": _USER, "password": _PASS},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert COOKIE_NAME in resp.cookies
    assert verify_session_token(resp.cookies[COOKIE_NAME], _SECRET)


def test_login_wrong_password_redirects_with_error(client, auth_config):
    resp = client.post(
        "/auth/login",
        data={"username": _USER, "password": "wrongpass"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "login_error=1" in resp.headers["location"]
    assert COOKIE_NAME not in resp.cookies


def test_login_logs_failed_attempt(client, auth_config, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        client.post(
            "/auth/login",
            data={"username": "attacker", "password": "guess"},
            follow_redirects=False,
        )
    assert any("Failed login attempt" in r.message for r in caplog.records)
    assert any("attacker" in r.message for r in caplog.records)


# ── GET /auth/logout ───────────────────────────────────────────────────────────


def test_logout_clears_cookie(client, auth_config):
    token = create_session_token(_SECRET, _USER)
    client.cookies.set(COOKIE_NAME, token)
    resp = client.get("/auth/logout", follow_redirects=False)
    client.cookies.clear()
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    # Cookie should be cleared (max_age=0 or deleted)
    assert COOKIE_NAME not in resp.cookies or resp.cookies[COOKIE_NAME] == ""


# ── /static/ public access ────────────────────────────────────────────────────


def test_static_landing_accessible_without_auth(client, auth_config):
    """Missing file returns 404, NOT 401 — confirms auth bypass works."""
    resp = client.get("/static/landing/nonexistent.png")
    assert resp.status_code == 404


def test_static_aap_css_accessible_without_auth(client, auth_config):
    """Landing page CSS (tokens.css, app.css) must be publicly accessible.

    Without this, the browser shows a native Basic Auth dialog instead of
    rendering the landing page.  A 404 (file not found) is acceptable; 401 is not.
    """
    for path in ("/static/aap/tokens.css", "/static/aap/app.css"):
        resp = client.get(path)
        assert resp.status_code != 401, f"{path} returned 401 — will block landing page"


# ── unauthenticated non-root redirect ─────────────────────────────────────────


def test_unauthenticated_page_path_redirects_to_landing(client, auth_config):
    """Non-root HTML paths redirect to / so browsers show the login form."""
    resp = client.get("/some-page", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_unauthenticated_api_path_returns_401(client, auth_config):
    """API paths keep 401 + WWW-Authenticate for curl/programmatic access."""
    resp = client.get("/api/series", follow_redirects=False)
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
