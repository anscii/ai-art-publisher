#!/usr/bin/env python3
"""
Run DB schema setup + Alembic migrations.

- Fresh install: create_all builds tables with current schema, then stamp head
  so Alembic knows migrations are already applied.
- Existing install: create_all is a no-op (tables exist), then upgrade head
  applies any pending migrations.
"""

import os
import sys

# Ensure the project root is on sys.path regardless of how the script is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from alembic import command
from alembic.config import Config
from app.database import Base, engine
from app.models import Base as _  # noqa: F401 — registers all ORM models


def main() -> None:
    inspector = inspect(engine)
    fresh = not inspector.has_table("series")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    if fresh:
        # Fresh DB — create schema then stamp (no migrations needed).
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
        print("Fresh install: tables created and stamped at head.")
    else:
        # Existing DB — migrations handle all schema changes.
        command.upgrade(cfg, "head")
        print("Existing install: migrations applied.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
