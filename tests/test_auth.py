import base64

import pytest

from app.config import AppConfig
from app.routers.auth import COOKIE_NAME, create_session_token, verify_session_token

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


# ── GET / routing ──────────────────────────────────────────────────────────────


def test_root_no_auth_configured_returns_app(client):
    """Auth disabled in tests by default — GET / returns the app HTML."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AI Art Publisher" in resp.text


def test_root_unauthenticated_returns_landing(client, auth_config):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    # Landing page has the login modal, app HTML does not
    assert "loginModal" in resp.text


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


# ── /static/landing/ public access ────────────────────────────────────────────


def test_static_landing_accessible_without_auth(client, auth_config):
    """Missing file returns 404, NOT 401 — confirms auth bypass works."""
    resp = client.get("/static/landing/nonexistent.png")
    assert resp.status_code == 404
