"""add title_ru to ai_variants and series

Revision ID: 014
Revises: 013
Create Date: 2026-05-15
"""

import sqlalchemy as sa

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_variants",
        sa.Column("title_ru", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "series",
        sa.Column("title_ru", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("ai_variants", "title_ru")
    op.drop_column("series", "title_ru")
