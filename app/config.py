import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/db.sqlite")
    data_dir: str = os.getenv("DATA_DIR", "./data")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    auth_username: str = os.getenv("AUTH_USERNAME", "")
    auth_password: str = os.getenv("AUTH_PASSWORD", "")
    fake_posting: bool = os.getenv("FAKE_POSTING", "false").lower() == "true"
    fake_ai: bool = os.getenv("FAKE_AI", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    local_storage: bool = os.getenv("LOCAL_STORAGE", "false").lower() in ("1", "true")
    scheduler_secret: str = os.getenv("SCHEDULER_SECRET", "")
    backup_token: str = os.getenv("BACKUP_TOKEN", "")
    backup_retention_days: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
