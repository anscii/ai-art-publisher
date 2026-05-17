"""add variant_id to posts

Revision ID: 018
Revises: 017
Create Date: 2026-05-17
"""

import sqlalchemy as sa

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("variant_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "variant_id")
