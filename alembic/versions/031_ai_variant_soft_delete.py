"""ai_variants: add deleted_at for soft delete

Revision ID: 031
Revises: 030
Create Date: 2026-06-07
"""

import sqlalchemy as sa

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_variants") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_ai_variants_deleted_at", ["deleted_at"])


def downgrade() -> None:
    with op.batch_alter_table("ai_variants") as batch_op:
        batch_op.drop_index("ix_ai_variants_deleted_at")
        batch_op.drop_column("deleted_at")
