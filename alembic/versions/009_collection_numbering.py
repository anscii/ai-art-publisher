"""add collection_index, collection_number to Series; collection_line to Post

Revision ID: 009
Revises: 008
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    series_cols = {c["name"] for c in inspector.get_columns("series")}
    post_cols = {c["name"] for c in inspector.get_columns("posts")}

    if "collection_index" not in series_cols:
        op.add_column("series", sa.Column("collection_index", sa.Integer(), nullable=True))
    if "collection_number" not in series_cols:
        op.add_column("series", sa.Column("collection_number", sa.String(), nullable=True))
    if "collection_line" not in post_cols:
        op.add_column("posts", sa.Column("collection_line", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    series_cols = {c["name"] for c in inspector.get_columns("series")}
    post_cols = {c["name"] for c in inspector.get_columns("posts")}

    if "collection_number" in series_cols:
        op.drop_column("series", "collection_number")
    if "collection_index" in series_cols:
        op.drop_column("series", "collection_index")
    if "collection_line" in post_cols:
        op.drop_column("posts", "collection_line")
