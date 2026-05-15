"""add chosen_variant_id to series

Revision ID: 015
Revises: 014
Create Date: 2026-05-15
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("series", sa.Column("chosen_variant_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("series", "chosen_variant_id")
