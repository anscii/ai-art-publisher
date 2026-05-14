"""add name_ru to Collection; add title_ru, collection_line_ru to Post

Revision ID: 010
Revises: 009
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    coll_cols = {c["name"] for c in inspector.get_columns("collections")}
    post_cols = {c["name"] for c in inspector.get_columns("posts")}

    if "name_ru" not in coll_cols:
        op.add_column("collections", sa.Column("name_ru", sa.String(), nullable=True))
    if "title_ru" not in post_cols:
        op.add_column(
            "posts", sa.Column("title_ru", sa.String(), nullable=False, server_default="")
        )
    if "collection_line_ru" not in post_cols:
        op.add_column("posts", sa.Column("collection_line_ru", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    coll_cols = {c["name"] for c in inspector.get_columns("collections")}
    post_cols = {c["name"] for c in inspector.get_columns("posts")}

    if "name_ru" in coll_cols:
        op.drop_column("collections", "name_ru")
    if "collection_line_ru" in post_cols:
        op.drop_column("posts", "collection_line_ru")
    if "title_ru" in post_cols:
        op.drop_column("posts", "title_ru")
