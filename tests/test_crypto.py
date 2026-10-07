from cryptography.fernet import Fernet

from app.config import AppConfig
from app.crypto import decrypt, encrypt


def test_round_trip_and_ciphertext_differs():
    token = encrypt("sk-secret")
    assert token != "sk-secret"
    assert token.startswith("gAAAA")
    assert decrypt(token) == "sk-secret"


def test_empty_stays_empty():
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_wrong_key_returns_empty(monkeypatch):
    token = encrypt("sk-secret")
    monkeypatch.setattr(AppConfig, "settings_encryption_key", Fernet.generate_key().decode())
    assert decrypt(token) == ""


def test_derives_key_from_session_secret_when_unset(monkeypatch):
    monkeypatch.setattr(AppConfig, "settings_encryption_key", "")
    assert decrypt(encrypt("sk-secret")) == "sk-secret"
