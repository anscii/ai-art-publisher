"""add text_halign to story_frames

Revision ID: 027
Revises: 026
Create Date: 2026-05-29
"""

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.add_column(
            sa.Column("text_halign", sa.String(), nullable=False, server_default="center")
        )


def downgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.drop_column("text_halign")
