import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_config

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
