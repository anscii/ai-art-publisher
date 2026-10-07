"""ai_requests ledger + Default AI Access settings

Renames app_settings.openrouter_api_key -> default_ai_openrouter_key and adds
default_ai_daily_limit (Quota per User per UTC day, 0 = off).

Revision ID: 038
Revises: 037
Create Date: 2026-10-07
"""

import sqlalchemy as sa

from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("via_default_access", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_requests_user_created", "ai_requests", ["user_id", "created_at"])

    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column("openrouter_api_key", new_column_name="default_ai_openrouter_key")
        batch_op.add_column(
            sa.Column("default_ai_daily_limit", sa.Integer(), nullable=False, server_default="20")
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.drop_column("default_ai_daily_limit")
        batch_op.alter_column("default_ai_openrouter_key", new_column_name="openrouter_api_key")
    op.drop_index("ix_ai_requests_user_created", table_name="ai_requests")
    op.drop_table("ai_requests")
