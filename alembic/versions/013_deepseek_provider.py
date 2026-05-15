"""add deepseek provider fields

Revision ID: 013
Revises: 012
Create Date: 2026-05-15
"""

import sqlalchemy as sa

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("deepseek_api_key", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("deepseek_default_model", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "deepseek_default_model")
    op.drop_column("app_settings", "deepseek_api_key")
