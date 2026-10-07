from sqlalchemy import create_engine, inspect, text

from alembic import command as alembic_command
from alembic.config import Config
from app import models  # noqa: F401 — registers models with Base
from app.database import Base


def _setup(tmp_path, monkeypatch) -> tuple[Config, str]:
    from app.config import AppConfig

    db_url = f"sqlite:///{tmp_path / 'ai_requests_038.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    monkeypatch.setattr(AppConfig, "database_url", db_url)

    # Head schema, then undo 038.
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE ai_requests"))
        conn.execute(text("ALTER TABLE app_settings DROP COLUMN default_ai_daily_limit"))
        conn.execute(
            text(
                "ALTER TABLE app_settings RENAME COLUMN "
                "default_ai_openrouter_key TO openrouter_api_key"
            )
        )
    engine.dispose()
    alembic_command.stamp(cfg, "037")
    return cfg, db_url


def _insert_settings_row(db_url: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        cols = {
            c["name"]: ""
            for c in inspect(conn).get_columns("app_settings")
            if not c["nullable"] and c["name"] != "id"
        }
        cols["openrouter_api_key"] = "sk-or"
        names = ["id", *cols]
        conn.execute(
            text(
                f"INSERT INTO app_settings ({', '.join(names)}) "
                f"VALUES (1, {', '.join(':' + n for n in cols)})"
            ),
            cols,
        )
    engine.dispose()


def test_upgrade_renames_key_and_adds_limit_and_table(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    _insert_settings_row(db_url)

    alembic_command.upgrade(cfg, "038")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT * FROM app_settings")).mappings().one()
        tables = set(inspect(conn).get_table_names())
    engine.dispose()
    assert row["default_ai_openrouter_key"] == "sk-or"
    assert row["default_ai_daily_limit"] == 20
    assert "openrouter_api_key" not in row
    assert "ai_requests" in tables


def test_downgrade_restores_old_column_with_value(tmp_path, monkeypatch):
    cfg, db_url = _setup(tmp_path, monkeypatch)
    _insert_settings_row(db_url)
    alembic_command.upgrade(cfg, "038")

    alembic_command.downgrade(cfg, "037")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT * FROM app_settings")).mappings().one()
        tables = set(inspect(conn).get_table_names())
    engine.dispose()
    assert row["openrouter_api_key"] == "sk-or"
    assert "default_ai_openrouter_key" not in row
    assert "default_ai_daily_limit" not in row
    assert "ai_requests" not in tables
