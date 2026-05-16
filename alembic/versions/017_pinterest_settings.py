"""add pinterest settings

Revision ID: 017
Revises: 016
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("pinterest_access_token", sa.Text(), nullable=True))
    op.add_column(
        "app_settings", sa.Column("pinterest_default_board_id", sa.Text(), nullable=True)
    )
    op.add_column("app_settings", sa.Column("pinterest_board_map", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "pinterest_board_map")
    op.drop_column("app_settings", "pinterest_default_board_id")
    op.drop_column("app_settings", "pinterest_access_token")
