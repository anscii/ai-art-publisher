import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_config

config = get_config()

engine = create_engine(
    config.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_wal(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _bootstrap_settings(db):
    from app.models import AppSettings

    s = db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)
    env_map = {
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
        "default_provider": "DEFAULT_PROVIDER",
        "default_model": "DEFAULT_MODEL",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_channel_id": "TELEGRAM_CHANNEL_ID",
        "instagram_access_token": "INSTAGRAM_ACCESS_TOKEN",
        "instagram_user_id": "INSTAGRAM_USER_ID",
        "r2_endpoint": "R2_ENDPOINT",
        "r2_access_key": "R2_ACCESS_KEY",
        "r2_secret_key": "R2_SECRET_KEY",
        "r2_bucket": "R2_BUCKET",
        "r2_public_base_url": "R2_PUBLIC_BASE_URL",
    }
    for field, env_key in env_map.items():
        if not getattr(s, field) and os.getenv(env_key):
            setattr(s, field, os.getenv(env_key))
    db.commit()


def init_db():
    from app import models  # noqa: F401 — registers models with Base

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _bootstrap_settings(db)
    finally:
        db.close()
