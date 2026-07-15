import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.models import User

logger = logging.getLogger("app.auth")

router = APIRouter()

COOKIE_NAME = "session"
_MAX_AGE = 30 * 24 * 3600  # 30 days


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(secret: str, username: str) -> str:
    exp = int(time.time()) + _MAX_AGE
    payload = base64.urlsafe_b64encode(json.dumps({"u": username, "exp": exp}).encode()).decode()
    return f"{payload}.{_sign(payload, secret)}"


def verify_session_token(token: str, secret: str) -> bool:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload, secret), sig):
            return False
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(time.time()) <= data["exp"]
    except (ValueError, KeyError):
        return False


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
            owner = db.query(User).filter(User.email == cfg.owner_email.strip().lower()).first()
            if owner and not owner.banned_at:
                return owner

    if not cfg.auth_username and not cfg.google_client_id:
        # No auth configured at all (local dev / E2E) — same "auth disabled when
        # env unset" semantics the middleware already has. Resolve or create a
        # default local user so the app stays usable without OAuth setup.
        user = db.query(User).filter(User.email == "local@localhost").first()
        if not user:
            user = User(email="local@localhost", is_admin=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(status_code=401, detail="Unauthorized")


def _verify_credentials(username: str, password: str, cfg) -> bool:
    return secrets.compare_digest(username, cfg.auth_username) and secrets.compare_digest(
        password, cfg.auth_password
    )


def is_authenticated(request: Request, cfg) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    if token and verify_session_token(token, cfg.session_secret):
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

    token = create_session_token(cfg.session_secret, username)
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
