"""add post_url to posts

Revision ID: 021
Revises: 020
Create Date: 2026-05-23
"""

import sqlalchemy as sa

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("post_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "post_url")
