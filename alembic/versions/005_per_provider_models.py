"""per-provider default model fields

Revision ID: 005
Revises: 004
Create Date: 2026-05-12
"""

import sqlalchemy as sa

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("app_settings", "default_model")
    op.add_column(
        "app_settings",
        sa.Column("anthropic_default_model", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("openai_default_model", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("google_default_model", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "google_default_model")
    op.drop_column("app_settings", "openai_default_model")
    op.drop_column("app_settings", "anthropic_default_model")
    op.add_column(
        "app_settings",
        sa.Column("default_model", sa.String(), nullable=False, server_default="claude-haiku-4-5"),
    )
