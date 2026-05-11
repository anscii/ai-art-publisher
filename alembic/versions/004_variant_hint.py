"""add hint to ai_variants

Revision ID: 004
Revises: 003
Create Date: 2026-05-11
"""

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_variants", sa.Column("hint", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_variants", "hint")
