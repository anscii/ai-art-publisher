"""app_settings: add invite_code

Revision ID: 033
Revises: 032
Create Date: 2026-07-03
"""

import sqlalchemy as sa

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.add_column(
            sa.Column("invite_code", sa.String(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.drop_column("invite_code")
