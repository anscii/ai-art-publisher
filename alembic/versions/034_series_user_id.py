"""series: add user_id, backfill onto OWNER_EMAIL account

Revision ID: 034
Revises: 033
Create Date: 2026-07-03
"""

import os
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lowercased to match the callback's email normalization — a case mismatch
    # here would silently create a second owner account on first Google login.
    owner_email = os.getenv("OWNER_EMAIL", "").strip().lower()
    if not owner_email:
        raise RuntimeError(
            "OWNER_EMAIL env var must be set before running this migration — "
            "it becomes the account existing Series data is assigned to."
        )

    bind = op.get_bind()

    owner_row = bind.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": owner_email}
    ).fetchone()
    if owner_row:
        owner_id = owner_row[0]
    else:
        owner_id = str(uuid.uuid4())
        bind.execute(
            text(
                "INSERT INTO users (id, email, google_sub, is_admin, created_at) "
                "VALUES (:id, :email, NULL, 1, :created)"
            ),
            {"id": owner_id, "email": owner_email, "created": datetime.utcnow().isoformat()},
        )

    with op.batch_alter_table("series") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))

    bind.execute(text("UPDATE series SET user_id = :owner_id"), {"owner_id": owner_id})

    with op.batch_alter_table("series") as batch_op:
        batch_op.alter_column("user_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_series_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_series_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("series") as batch_op:
        batch_op.drop_index("ix_series_user_id")
        batch_op.drop_constraint("fk_series_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
