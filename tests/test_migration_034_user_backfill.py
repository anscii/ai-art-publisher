from sqlalchemy import create_engine, text

from alembic import command as alembic_command
from alembic.config import Config
from app import models  # noqa: F401 — registers models with Base
from app.database import Base


def _cfg_for(db_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_backfill_assigns_existing_series_to_owner(tmp_path, monkeypatch):
    from app.config import AppConfig

    db_path = tmp_path / "backfill_test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _cfg_for(db_url)

    # Patch AppConfig so alembic's env.py uses the test DB.
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Create ORM schema and stamp at 033 (the last migration before ours).
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    alembic_command.stamp(cfg, "033")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO series (id, name, title, title_ru, description_en, "
                "description_ru, tags_instagram, tags_telegram, status, created_at, "
                "generation_status) VALUES "
                "('s1', 'Old Series', '', '', '', '', '[]', '[]', 'new', "
                "'2026-01-01 00:00:00', 'idle')"
            )
        )
    engine.dispose()

    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    alembic_command.upgrade(cfg, "034")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        owner_row = conn.execute(
            text("SELECT id, is_admin FROM users WHERE email = 'owner@example.com'")
        ).fetchone()
        assert owner_row is not None
        assert owner_row[1] in (1, True)

        series_row = conn.execute(text("SELECT user_id FROM series WHERE id = 's1'")).fetchone()
        assert series_row[0] == owner_row[0]

        cols = {c[1] for c in conn.execute(text("PRAGMA table_info(series)")).fetchall()}
        assert "user_id" in cols
    engine.dispose()


def test_backfill_requires_owner_email(tmp_path, monkeypatch):
    import pytest

    from app.config import AppConfig

    db_path = tmp_path / "backfill_missing_env.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _cfg_for(db_url)

    # Patch AppConfig so alembic's env.py uses the test DB.
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Create ORM schema and stamp at 033 (the last migration before ours).
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    alembic_command.stamp(cfg, "033")

    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="OWNER_EMAIL"):
        alembic_command.upgrade(cfg, "034")
