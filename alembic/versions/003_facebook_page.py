"""add facebook page cross-posting

Revision ID: 003
Revises: 002
Create Date: 2026-05-10
"""

import sqlalchemy as sa

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("facebook_page_id", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("facebook_page_access_token", sa.String(), nullable=False, server_default=""),
    )
    op.add_column("series", sa.Column("posted_to_facebook_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("series", "posted_to_facebook_at")
    op.drop_column("app_settings", "facebook_page_id")
    op.drop_column("app_settings", "facebook_page_access_token")
