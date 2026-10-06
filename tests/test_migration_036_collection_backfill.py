import pytest
from sqlalchemy import create_engine, text

from alembic import command as alembic_command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app import models  # noqa: F401 — registers models with Base
from app.database import Base


def _setup(tmp_path, monkeypatch) -> tuple[Config, str]:
    from app.config import AppConfig

    db_url = f"sqlite:///{tmp_path / 'backfill_036.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Head schema minus `collections.user_id`, as migration 036 finds it.
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        with Operations(MigrationContext.configure(conn)).batch_alter_table(
            "collections"
        ) as batch_op:
            batch_op.drop_index("ix_collections_user_id")
            batch_op.drop_column("user_id")
        conn.commit()
    engine.dispose()
    alembic_command.stamp(cfg, "035")
    return cfg, db_url


def _insert_user(conn, uid: str, is_admin: int, created: str) -> None:
    conn.execute(
        text(
            "INSERT INTO users (id, email, google_sub, is_admin, created_at) "
            "VALUES (:id, :email, NULL, :a, :c)"
        ),
        {"id": uid, "email": f"{uid}@example.com", "a": is_admin, "c": created},
    )


def _insert_collection(conn, cid: str) -> None:
    conn.execute(
        text(
            "INSERT INTO collections (id, name, created_at) VALUES (:id, 'c', '2026-01-01 00:00:00')"
        ),
        {"id": cid},
    )


def test_backfill_assigns_collections_to_oldest_admin(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        _insert_user(conn, "plain", 0, "2025-01-01 00:00:00")
        _insert_user(conn, "admin-new", 1, "2026-02-01 00:00:00")
        _insert_user(conn, "admin-old", 1, "2026-01-01 00:00:00")
        _insert_collection(conn, "c1")
        _insert_collection(conn, "c2")
    engine.dispose()

    alembic_command.upgrade(cfg, "036")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        owners = {r[0] for r in conn.execute(text("SELECT user_id FROM collections"))}
    engine.dispose()
    assert owners == {"admin-old"}


def test_fails_when_collections_but_no_admin(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        _insert_user(conn, "plain", 0, "2026-01-01 00:00:00")
        _insert_collection(conn, "c1")
    engine.dispose()

    with pytest.raises(RuntimeError, match="no admin"):
        alembic_command.upgrade(cfg, "036")


def test_empty_collections_without_admin_ok(tmp_path, monkeypatch):
    cfg, _ = _setup(tmp_path, monkeypatch)
    alembic_command.upgrade(cfg, "036")
