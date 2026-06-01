"""add generation_status and generation_error to series

Revision ID: 028
Revises: 027
Create Date: 2026-06-01
"""

import sqlalchemy as sa

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("series") as batch_op:
        batch_op.add_column(
            sa.Column("generation_status", sa.String(), nullable=False, server_default="idle")
        )
        batch_op.add_column(sa.Column("generation_error", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("series") as batch_op:
        batch_op.drop_column("generation_error")
        batch_op.drop_column("generation_status")
