"""add text_color, text_align, title_position to story_frames

Revision ID: 025
Revises: 024
Create Date: 2026-05-28
"""

import sqlalchemy as sa

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.add_column(
            sa.Column("text_color", sa.String(), nullable=False, server_default="#ffffff")
        )
        batch_op.add_column(
            sa.Column("text_align", sa.String(), nullable=False, server_default="middle")
        )
        batch_op.add_column(
            sa.Column("title_position", sa.String(), nullable=False, server_default="bottom")
        )


def downgrade() -> None:
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.drop_column("title_position")
        batch_op.drop_column("text_align")
        batch_op.drop_column("text_color")
