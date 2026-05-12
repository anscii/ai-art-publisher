"""add cost_usd to ai_variants

Revision ID: 006
Revises: 005
Create Date: 2026-05-12
"""

import sqlalchemy as sa

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_variants", sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("ai_variants", "cost_usd")
