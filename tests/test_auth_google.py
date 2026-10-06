import httpx
import respx

from app.config import AppConfig
from app.routers.auth import COOKIE_NAME, OAUTH_STATE_COOKIE

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _oauth_config(monkeypatch):
    monkeypatch.setattr(AppConfig, "google_client_id", "client-id")
    monkeypatch.setattr(AppConfig, "google_client_secret", "client-secret")
    monkeypatch.setattr(
        AppConfig, "google_oauth_redirect_uri", "https://app.test/auth/google/callback"
    )


def _set_invite_code(client, code="friends-2026"):
    client.put("/api/settings", json={"invite_code": code})


@respx.mock
def test_signup_wrong_invite_code_rejected(client, monkeypatch):
    _set_invite_code(client)
    _oauth_config(monkeypatch)
    resp = client.post("/auth/signup", data={"invite_code": "wrong"}, follow_redirects=False)
    assert resp.status_code == 303
    assert "invite_error=1" in resp.headers["location"]
    assert OAUTH_STATE_COOKIE not in resp.cookies


@respx.mock
def test_signup_correct_invite_code_redirects_to_google(client, monkeypatch):
    _set_invite_code(client)
    _oauth_config(monkeypatch)
    resp = client.post("/auth/signup", data={"invite_code": "friends-2026"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert OAUTH_STATE_COOKIE in resp.cookies


@respx.mock
def test_callback_new_user_with_valid_invite_creates_account(client, monkeypatch):
    _set_invite_code(client)
    _oauth_config(monkeypatch)
    signup_resp = client.post(
        "/auth/signup", data={"invite_code": "friends-2026"}, follow_redirects=False
    )
    state_cookie = signup_resp.cookies[OAUTH_STATE_COOKIE]
    location = signup_resp.headers["location"]
    state_param = location.split("state=")[1].split("&")[0]

    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200, json={"sub": "g-999", "email": "newfriend@example.com", "email_verified": True}
        )
    )

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert COOKIE_NAME in resp.cookies

    users_resp = client.get("/api/series")  # any authenticated call proves the cookie works
    assert users_resp.status_code != 401


@respx.mock
def test_callback_new_user_without_invite_rejected(client, monkeypatch):
    _oauth_config(monkeypatch)
    resp = client.get("/auth/login/google", follow_redirects=False)
    state_cookie = resp.cookies[OAUTH_STATE_COOKIE]
    location = resp.headers["location"]
    state_param = location.split("state=")[1].split("&")[0]

    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200, json={"sub": "g-000", "email": "stranger@example.com", "email_verified": True}
        )
    )

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    assert callback_resp.status_code == 303
    assert "login_error=no_account" in callback_resp.headers["location"]
    assert COOKIE_NAME not in callback_resp.cookies


@respx.mock
def test_callback_existing_user_logs_in(client, monkeypatch, db):
    from app.models import User

    _oauth_config(monkeypatch)
    db.add(User(email="existing@example.com", google_sub="g-existing"))
    db.commit()

    resp = client.get("/auth/login/google", follow_redirects=False)
    state_cookie = resp.cookies[OAUTH_STATE_COOKIE]
    location = resp.headers["location"]
    state_param = location.split("state=")[1].split("&")[0]

    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200,
            json={"sub": "g-existing", "email": "existing@example.com", "email_verified": True},
        )
    )

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    assert callback_resp.status_code == 303
    assert callback_resp.headers["location"] == "/"
    assert COOKIE_NAME in callback_resp.cookies


@respx.mock
def test_callback_state_mismatch_rejected(client, monkeypatch):
    _oauth_config(monkeypatch)
    resp = client.get("/auth/login/google", follow_redirects=False)
    state_cookie = resp.cookies[OAUTH_STATE_COOKIE]

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        "/auth/google/callback?code=fake-code&state=wrong-nonce", follow_redirects=False
    )
    assert callback_resp.status_code == 303
    assert "login_error" in callback_resp.headers["location"]


@respx.mock
def test_callback_unverified_email_rejected(client, monkeypatch):
    """Security: an unverified Google email must never create or link an account.

    The owner row from migration 035 has google_sub=NULL and gets linked by
    email match on first login — without this check, a Google account carrying
    OWNER_EMAIL as an unverified external email could claim it (admin takeover).
    """
    _set_invite_code(client)
    _oauth_config(monkeypatch)
    signup_resp = client.post(
        "/auth/signup", data={"invite_code": "friends-2026"}, follow_redirects=False
    )
    state_cookie = signup_resp.cookies[OAUTH_STATE_COOKIE]
    state_param = signup_resp.headers["location"].split("state=")[1].split("&")[0]

    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200, json={"sub": "g-777", "email": "victim@example.com", "email_verified": False}
        )
    )

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    assert callback_resp.status_code == 303
    assert "login_error" in callback_resp.headers["location"]
    assert COOKIE_NAME not in callback_resp.cookies


def test_auth_routes_public_without_credentials(client, monkeypatch, auth_config):
    resp = client.get("/auth/login/google", follow_redirects=False)
    assert resp.status_code != 401

    resp = client.post("/auth/signup", data={"invite_code": "x"}, follow_redirects=False)
    assert resp.status_code != 401

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code != 401


def test_middleware_enforces_when_only_google_configured(client, monkeypatch):
    """Google-OAuth-only deployment (legacy creds unset) must not leave the
    unscoped routers (images/posts/settings/...) reachable anonymously."""
    monkeypatch.setattr(AppConfig, "google_client_id", "client-id")
    resp = client.get("/api/images", follow_redirects=False)
    assert resp.status_code in (401, 404)  # 401 from middleware, never a 200 payload

    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_signup_page_has_invite_form_and_google_link(client):
    resp = client.get("/auth/signup")
    assert resp.status_code == 200
    assert "<form" in resp.text
    assert 'name="invite_code"' in resp.text
    assert "/auth/login/google" in resp.text


def test_landing_page_links_to_signup(client, auth_config):
    resp = client.get("/")
    assert "/auth/signup" in resp.text


@respx.mock
def test_callback_email_match_with_different_google_sub_rejected(client, monkeypatch, db):
    """Account takeover guard: user A registered with sub X; the same email later
    shows up under a different Google account (sub Y). Must NOT log in as A."""
    from app.models import User

    _oauth_config(monkeypatch)
    db.add(User(email="recycled@example.com", google_sub="g-original"))
    db.commit()

    resp = client.get("/auth/login/google", follow_redirects=False)
    state_cookie = resp.cookies[OAUTH_STATE_COOKIE]
    state_param = resp.headers["location"].split("state=")[1].split("&")[0]

    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200,
            json={"sub": "g-newcomer", "email": "recycled@example.com", "email_verified": True},
        )
    )

    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    client.cookies.clear()
    assert callback_resp.status_code == 303
    assert "login_error=no_account" in callback_resp.headers["location"]
    assert COOKIE_NAME not in callback_resp.cookies
    assert db.query(User).filter(User.email == "recycled@example.com").one().google_sub == (
        "g-original"
    )


@respx.mock
def test_callback_links_owner_row_with_null_sub(client, monkeypatch, db):
    """Migration 034 creates the owner with google_sub=NULL; first Google login links it."""
    from app.models import User

    _oauth_config(monkeypatch)
    db.add(User(email="owner@example.com", google_sub=None, is_admin=True))
    db.commit()

    resp = client.get("/auth/login/google", follow_redirects=False)
    state_cookie = resp.cookies[OAUTH_STATE_COOKIE]
    state_param = resp.headers["location"].split("state=")[1].split("&")[0]
    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(GOOGLE_USERINFO_URL).mock(
        return_value=httpx.Response(
            200, json={"sub": "g-owner", "email": "owner@example.com", "email_verified": True}
        )
    )
    client.cookies.set(OAUTH_STATE_COOKIE, state_cookie)
    callback_resp = client.get(
        f"/auth/google/callback?code=fake-code&state={state_param}", follow_redirects=False
    )
    client.cookies.clear()
    assert callback_resp.headers["location"] == "/"
    assert COOKIE_NAME in callback_resp.cookies
    assert db.query(User).filter(User.email == "owner@example.com").one().google_sub == "g-owner"


def test_google_redirect_url_is_percent_encoded(client, monkeypatch):
    _oauth_config(monkeypatch)
    resp = client.get("/auth/login/google", follow_redirects=False)
    location = resp.headers["location"]
    assert "redirect_uri=https%3A%2F%2Fapp.test%2Fauth%2Fgoogle%2Fcallback" in location
    assert "scope=openid+email" in location


def test_login_google_without_config_redirects_error(client):
    """reset_config blanks google_client_id — the link must not bounce to Google with an empty client_id."""
    resp = client.get("/auth/login/google", follow_redirects=False)
    assert resp.status_code == 303
    assert "login_error=google_off" in resp.headers["location"]


def test_landing_page_has_google_sign_in(client, auth_config):
    resp = client.get("/", follow_redirects=False)
    assert 'href="/auth/login/google"' in resp.text
