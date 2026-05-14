"""make posts.error_message nullable

Revision ID: 011
Revises: 010
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    # Check if column is already nullable (fresh installs created it correctly)
    cols = {c["name"]: c for c in inspector.get_columns("posts")}
    if cols.get("error_message", {}).get("nullable", True):
        return

    # SQLite can't ALTER COLUMN — rebuild the table
    with op.batch_alter_table("posts", recreate="always") as batch_op:
        batch_op.alter_column("error_message", existing_type=sa.String(), nullable=True)

    # Normalize empty strings to NULL
    bind.execute(text("UPDATE posts SET error_message = NULL WHERE error_message = ''"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("UPDATE posts SET error_message = '' WHERE error_message IS NULL"))

    with op.batch_alter_table("posts", recreate="always") as batch_op:
        batch_op.alter_column(
            "error_message",
            existing_type=sa.String(),
            nullable=False,
            server_default=sa.text("''"),
        )
