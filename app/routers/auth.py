import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.models import AppSettings, User

logger = logging.getLogger("app.auth")

router = APIRouter()

COOKIE_NAME = "session"
_MAX_AGE = 30 * 24 * 3600  # 30 days

OAUTH_STATE_COOKIE = "oauth_state"
_OAUTH_STATE_MAX_AGE = 600  # 10 minutes

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def auth_enabled(cfg) -> bool:
    """Single source of truth for 'is any auth configured' — middleware and
    get_current_user must agree, or a half-set AUTH_USERNAME lets the
    middleware through while every /api call 401s."""
    return bool(cfg.auth_username and cfg.auth_password) or bool(cfg.google_client_id)


def _resolve_owner(db: Session, cfg) -> User | None:
    email = cfg.owner_email.strip().lower()
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


def _get_or_create_local_user(db: Session) -> User:
    user = db.query(User).filter(User.email == "local@localhost").first()
    if user:
        return user
    try:
        user = User(email="local@localhost", is_admin=True)
        db.add(user)
        db.commit()
    except IntegrityError:
        # Two first requests raced on the unique email index — the other one won.
        db.rollback()
        user = db.query(User).filter(User.email == "local@localhost").one()
    db.refresh(user)
    return user


def create_user_session_token(secret: str, user_id: str) -> str:
    exp = int(time.time()) + _MAX_AGE
    payload = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": exp}).encode()).decode()
    return f"{payload}.{_sign(payload, secret)}"


def get_session_user_id(request: Request, secret: str) -> str | None:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        return None
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload, secret), sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if int(time.time()) > data["exp"]:
            return None
        return data.get("uid")
    except (ValueError, KeyError):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    cfg = get_config()
    user_id = get_session_user_id(request, cfg.session_secret)
    if user_id:
        user = db.get(User, user_id)
        if user and not user.banned_at:
            return user
        raise HTTPException(status_code=401, detail="Unauthorized")

    auth = request.headers.get("Authorization", "")
    if cfg.auth_username and auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(status_code=401, detail="Unauthorized")
        if _verify_credentials(username, password, cfg):
            owner = _resolve_owner(db, cfg)
            if owner and not owner.banned_at:
                return owner

    if not auth_enabled(cfg):
        # No auth configured (local dev / E2E) — resolve or create a default
        # local user so the app stays usable without OAuth setup.
        user = _get_or_create_local_user(db)
        if user.banned_at:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user

    raise HTTPException(status_code=401, detail="Unauthorized")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _verify_credentials(username: str, password: str, cfg) -> bool:
    return secrets.compare_digest(username, cfg.auth_username) and secrets.compare_digest(
        password, cfg.auth_password
    )


def is_authenticated(request: Request, cfg) -> bool:
    if get_session_user_id(request, cfg.session_secret):
        return True
    if not cfg.auth_username or not cfg.auth_password:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
            return _verify_credentials(username, password, cfg)
        except (ValueError, UnicodeDecodeError):
            pass
    return False


@router.post("/auth/login", include_in_schema=False)
async def login(
    request: Request,
    username: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db),
):
    cfg = get_config()
    ok = bool(cfg.auth_username) and _verify_credentials(username, password, cfg)
    if not ok:
        logger.warning(
            "Failed login attempt: username=%r ip=%s",
            username,
            request.client.host if request.client else "unknown",
        )
        return RedirectResponse("/?login_error=1", status_code=303)

    # Password login is the owner's break-glass path: it must land on the same
    # uid-carrying token Google login issues, or get_current_user 401s every API call.
    owner = _resolve_owner(db, cfg)
    if not owner:
        logger.warning("Password login succeeded but OWNER_EMAIL has no matching user row")
        return RedirectResponse("/?login_error=no_owner", status_code=303)
    if owner.banned_at:
        return RedirectResponse("/?login_error=banned", status_code=303)

    token = create_user_session_token(cfg.session_secret, owner.id)
    is_https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=is_https,
        max_age=_MAX_AGE,
    )
    return resp


@router.get("/auth/logout", include_in_schema=False)
async def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


def _create_oauth_state_cookie_value(secret: str, nonce: str, invite_ok: bool) -> str:
    exp = int(time.time()) + _OAUTH_STATE_MAX_AGE
    payload = base64.urlsafe_b64encode(
        json.dumps({"nonce": nonce, "invite_ok": invite_ok, "exp": exp}).encode()
    ).decode()
    return f"{payload}.{_sign(payload, secret)}"


def _read_oauth_state_cookie(request: Request, secret: str) -> dict | None:
    token = request.cookies.get(OAUTH_STATE_COOKIE, "")
    if not token:
        return None
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload, secret), sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if int(time.time()) > data["exp"]:
            return None
        return data
    except (ValueError, KeyError):
        return None


def _redirect_to_google(cfg, invite_ok: bool) -> RedirectResponse:
    if not cfg.google_client_id:
        return RedirectResponse("/?login_error=google_off", status_code=303)
    nonce = secrets.token_urlsafe(24)
    params = {
        "client_id": cfg.google_client_id,
        "redirect_uri": cfg.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": nonce,
        "prompt": "select_account",
    }
    resp = RedirectResponse(f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", status_code=303)
    resp.set_cookie(
        OAUTH_STATE_COOKIE,
        _create_oauth_state_cookie_value(cfg.session_secret, nonce, invite_ok),
        httponly=True,
        samesite="lax",
        max_age=_OAUTH_STATE_MAX_AGE,
    )
    return resp


@router.get("/auth/login/google", include_in_schema=False)
def login_google():
    cfg = get_config()
    return _redirect_to_google(cfg, invite_ok=False)


_SIGNUP_HTML = """<!doctype html>
<html><head><title>Sign up — AI Art Publisher</title></head>
<body>
<h1>Sign up</h1>
{error}
<form method="post" action="/auth/signup">
  <label>Invite code <input type="text" name="invite_code" required></label>
  <button type="submit">Continue</button>
</form>
<p><a href="/auth/login/google">Already have an account? Sign in with Google</a></p>
</body></html>"""


@router.get("/auth/signup", include_in_schema=False)
async def signup_page(invite_error: str = ""):
    error = "<p>Invalid invite code.</p>" if invite_error else ""
    return HTMLResponse(_SIGNUP_HTML.format(error=error))


@router.post("/auth/signup", include_in_schema=False)
def signup(request: Request, invite_code: str = Form()):
    cfg = get_config()
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        settings = db.get(AppSettings, 1)
        expected = settings.invite_code if settings else ""
        valid = bool(expected) and secrets.compare_digest(invite_code, expected)
    finally:
        db.close()
    if not valid:
        return RedirectResponse("/auth/signup?invite_error=1", status_code=303)
    return _redirect_to_google(cfg, invite_ok=True)


@router.get("/auth/google/callback", include_in_schema=False)
def google_callback(request: Request, code: str = "", state: str = ""):
    from app.database import SessionLocal

    cfg = get_config()
    state_data = _read_oauth_state_cookie(request, cfg.session_secret)
    resp_error = RedirectResponse("/?login_error=1", status_code=303)
    resp_error.delete_cookie(OAUTH_STATE_COOKIE)
    if not state_data or not code:
        return resp_error
    if not hmac.compare_digest(state_data["nonce"], state):
        return resp_error

    token_resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": cfg.google_client_id,
            "client_secret": cfg.google_client_secret,
            "redirect_uri": cfg.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if token_resp.status_code != 200:
        return resp_error
    access_token = token_resp.json().get("access_token", "")

    userinfo_resp = httpx.get(
        GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    if userinfo_resp.status_code != 200:
        return resp_error
    userinfo = userinfo_resp.json()
    google_sub = userinfo.get("sub", "")
    # Lowercase: Google emails are case-insensitive; email-match linking and the
    # OWNER_EMAIL backfill match must not silently miss on case.
    email = (userinfo.get("email") or "").strip().lower()
    # email_verified check is security-critical: the owner row (migration 034)
    # has google_sub=NULL and is linked by email match on first login. Without
    # this, a Google account carrying an unverified copy of OWNER_EMAIL could
    # claim the admin account.
    if not google_sub or not email or userinfo.get("email_verified") is not True:
        return resp_error

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == google_sub).first()
        if not user:
            user = db.query(User).filter(User.email == email).first()
            if user and user.google_sub:
                # Same email, different Google account (sub lookup above missed):
                # a recycled address must not log into the old owner's account.
                resp = RedirectResponse("/?login_error=no_account", status_code=303)
                resp.delete_cookie(OAUTH_STATE_COOKIE)
                return resp
            if user:
                # Owner row from migration 034 has google_sub=NULL — link on first login.
                user.google_sub = google_sub
                db.commit()
                db.refresh(user)
        if not user:
            if not state_data.get("invite_ok"):
                resp = RedirectResponse("/?login_error=no_account", status_code=303)
                resp.delete_cookie(OAUTH_STATE_COOKIE)
                return resp
            user = User(email=email, google_sub=google_sub)
            db.add(user)
            db.commit()
            db.refresh(user)
        if user.banned_at:
            resp = RedirectResponse("/?login_error=banned", status_code=303)
            resp.delete_cookie(OAUTH_STATE_COOKIE)
            return resp

        token = create_user_session_token(cfg.session_secret, user.id)
    finally:
        db.close()

    is_https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(OAUTH_STATE_COOKIE)
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=is_https,
        max_age=_MAX_AGE,
    )
    return resp
