"""add soft delete

Revision ID: 002
Revises: 001
Create Date: 2026-05-09
"""

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("series", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("images", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("images", "deleted_at")
    op.drop_column("series", "deleted_at")
