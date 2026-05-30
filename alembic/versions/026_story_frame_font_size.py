"""add font_size to story_frames

Revision ID: 026
Revises: 025
Create Date: 2026-05-28
"""

import sqlalchemy as sa

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.add_column(sa.Column("font_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.drop_column("font_size")
