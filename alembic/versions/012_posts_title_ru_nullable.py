"""make posts.title_ru nullable

Revision ID: 012
Revises: 011
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"]: c for c in inspector.get_columns("posts")}

    if "title_ru" not in cols:
        op.add_column("posts", sa.Column("title_ru", sa.String(), nullable=True))
        return

    if cols["title_ru"].get("nullable", True):
        return

    with op.batch_alter_table("posts", recreate="always") as batch_op:
        batch_op.alter_column("title_ru", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("UPDATE posts SET title_ru = '' WHERE title_ru IS NULL"))

    with op.batch_alter_table("posts", recreate="always") as batch_op:
        batch_op.alter_column(
            "title_ru",
            existing_type=sa.String(),
            nullable=False,
            server_default=sa.text("''"),
        )
