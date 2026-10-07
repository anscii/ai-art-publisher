import pytest
from sqlalchemy import create_engine, inspect, text

from alembic import command as alembic_command
from alembic.config import Config
from app import models  # noqa: F401 — registers models with Base
from app.crypto import decrypt
from app.database import Base

_OLD_COLS = [
    "anthropic_api_key",
    "openai_api_key",
    "google_api_key",
    "deepseek_api_key",
    "default_provider",
    "anthropic_default_model",
    "openai_default_model",
    "google_default_model",
    "deepseek_default_model",
    "openrouter_default_model",
    "image_edit_model",
]


def _setup(tmp_path, monkeypatch) -> tuple[Config, str]:
    from app.config import AppConfig

    db_url = f"sqlite:///{tmp_path / 'user_settings_037.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Head schema minus user_settings, plus the 11 old app_settings columns.
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE user_settings"))
        # undo 038
        conn.execute(text("DROP TABLE ai_requests"))
        conn.execute(text("ALTER TABLE app_settings DROP COLUMN default_ai_daily_limit"))
        conn.execute(
            text(
                "ALTER TABLE app_settings RENAME COLUMN "
                "default_ai_openrouter_key TO openrouter_api_key"
            )
        )
        for c in _OLD_COLS:
            conn.execute(
                text(f"ALTER TABLE app_settings ADD COLUMN {c} VARCHAR NOT NULL DEFAULT ''")
            )
    engine.dispose()
    alembic_command.stamp(cfg, "036")
    return cfg, db_url


def _insert_user(conn, uid: str, is_admin: int, created: str) -> None:
    conn.execute(
        text(
            "INSERT INTO users (id, email, google_sub, is_admin, created_at) "
            "VALUES (:id, :email, NULL, :a, :c)"
        ),
        {"id": uid, "email": f"{uid}@example.com", "a": is_admin, "c": created},
    )


def _insert_app_settings(conn, **vals) -> None:
    # Every NOT NULL column gets '' unless overridden.
    cols = {
        c["name"]: vals.get(c["name"], "")
        for c in inspect(conn).get_columns("app_settings")
        if not c["nullable"] and c["name"] != "id"
    }
    cols.update(vals)
    names = ["id", *cols]
    conn.execute(
        text(
            f"INSERT INTO app_settings ({', '.join(names)}) "
            f"VALUES (1, {', '.join(':' + n for n in cols)})"
        ),
        cols,
    )


def test_owner_keys_copied_encrypted_and_columns_dropped(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        _insert_user(conn, "plain", 0, "2025-01-01 00:00:00")
        _insert_user(conn, "admin-new", 1, "2026-02-01 00:00:00")
        _insert_user(conn, "admin-old", 1, "2026-01-01 00:00:00")
        _insert_app_settings(
            conn,
            anthropic_api_key="sk-owner",
            default_provider="anthropic",
            image_edit_model="img-m",
        )
    engine.dispose()

    alembic_command.upgrade(cfg, "037")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT * FROM user_settings")).mappings().all()
        cols = {c["name"] for c in inspect(conn).get_columns("app_settings")}
    engine.dispose()
    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == "admin-old"
    assert row["anthropic_api_key"] != "sk-owner"
    assert decrypt(row["anthropic_api_key"]) == "sk-owner"
    assert row["openai_api_key"] == ""
    assert row["default_provider"] == "anthropic"
    assert row["image_edit_model"] == "img-m"
    assert not cols & set(_OLD_COLS)
    assert "openrouter_api_key" in cols


def test_fails_when_keys_but_no_admin(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        _insert_user(conn, "plain", 0, "2026-01-01 00:00:00")
        _insert_app_settings(conn, openai_api_key="sk-x")
    engine.dispose()

    with pytest.raises(RuntimeError, match="no admin"):
        alembic_command.upgrade(cfg, "037")


def test_no_app_settings_row_ok(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    alembic_command.upgrade(cfg, "037")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM user_settings")).scalar() == 0
    engine.dispose()


def test_downgrade_restores_columns_empty(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    alembic_command.upgrade(cfg, "037")
    alembic_command.downgrade(cfg, "036")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("app_settings")}
        assert not inspect(conn).has_table("user_settings")
    engine.dispose()
    assert set(_OLD_COLS) <= cols
