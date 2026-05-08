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


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
