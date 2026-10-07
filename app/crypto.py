import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config import get_config


def _fernet() -> Fernet:
    cfg = get_config()
    key = cfg.settings_encryption_key
    if not key:
        # ponytail: derive from session_secret so dev/tests need no extra env; set
        # SETTINGS_ENCRYPTION_KEY in prod so rotating the session secret keeps keys readable
        digest = hashlib.sha256(f"settings:{cfg.session_secret}".encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""  # wrong key: treat as unset, user re-enters


class EncryptedStr(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value or "")

    def process_result_value(self, value, dialect):
        return decrypt(value or "")
