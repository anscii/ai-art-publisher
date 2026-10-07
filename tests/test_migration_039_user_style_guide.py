from sqlalchemy import create_engine, inspect, text

from alembic import command as alembic_command
from alembic.config import Config
from app import models  # noqa: F401 — registers models with Base
from app.database import Base


def _setup(tmp_path, monkeypatch) -> tuple[Config, str]:
    from app.config import AppConfig

    db_url = f"sqlite:///{tmp_path / 'style_guide_039.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Head schema, then undo 039.
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_settings DROP COLUMN style_guide"))
    engine.dispose()
    alembic_command.stamp(cfg, "038")
    return cfg, db_url


def _cols(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("user_settings")}
    engine.dispose()
    return cols


def test_upgrade_adds_column_with_empty_default(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, is_admin, created_at) VALUES ('u1', 'a@x.com', 0, '2026-01-01')"
            )
        )
        cols = {
            c["name"]: ""
            for c in inspect(conn).get_columns("user_settings")
            if not c["nullable"] and c["name"] != "user_id"
        }
        conn.execute(
            text(
                f"INSERT INTO user_settings (user_id, {', '.join(cols)}) "
                f"VALUES ('u1', {', '.join(':' + n for n in cols)})"
            ),
            cols,
        )
    engine.dispose()

    alembic_command.upgrade(cfg, "039")

    assert "style_guide" in _cols(db_url)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT style_guide FROM user_settings")).scalar() == ""
    engine.dispose()


def test_downgrade_drops_column(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    alembic_command.upgrade(cfg, "039")
    alembic_command.downgrade(cfg, "038")
    assert "style_guide" not in _cols(db_url)
