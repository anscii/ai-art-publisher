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


def test_decrypt_with_wrong_key_logs_warning(monkeypatch, caplog):
    import logging

    from app import crypto

    token = crypto.encrypt("sk-x")
    monkeypatch.setattr(AppConfig, "settings_encryption_key", Fernet.generate_key().decode())
    with caplog.at_level(logging.WARNING, logger="app.crypto"):
        assert crypto.decrypt(token) == ""
    assert "decrypt failed" in caplog.text


def test_check_key_rejects_malformed_key(monkeypatch):
    import pytest

    from app import crypto

    monkeypatch.setattr(AppConfig, "settings_encryption_key", "not-a-fernet-key")
    with pytest.raises(ValueError):
        crypto.check_key()
