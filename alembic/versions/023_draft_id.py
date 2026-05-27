"""add draft_id to ai_variants

Revision ID: 023
Revises: 022
Create Date: 2026-05-27
"""

import sqlalchemy as sa

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_variants", sa.Column("draft_id", sa.String(), nullable=True))
    with op.batch_alter_table("ai_variants") as batch_op:
        batch_op.create_foreign_key(
            "fk_ai_variants_draft_id",
            "ai_variants",
            ["draft_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_variants") as batch_op:
        batch_op.drop_constraint("fk_ai_variants_draft_id", type_="foreignkey")
    op.drop_column("ai_variants", "draft_id")
