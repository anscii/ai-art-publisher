"""add openrouter provider fields to app_settings

Revision ID: 019
Revises: 018
Create Date: 2026-05-19
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("openrouter_api_key", sa.String(), server_default="", nullable=False),
    )
    op.add_column(
        "app_settings",
        sa.Column("openrouter_default_model", sa.String(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "openrouter_api_key")
    op.drop_column("app_settings", "openrouter_default_model")
