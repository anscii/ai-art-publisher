"""drop old Series posting fields (notes, needs_review, review_reason, scheduled_*, posted_to_*)

Revision ID: 008
Revises: 007
Create Date: 2026-05-14
"""

import sqlalchemy as sa

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("series") as batch:
        batch.drop_column("scheduled_at")
        batch.drop_column("scheduled_targets")
        batch.drop_column("posted_to_telegram_at")
        batch.drop_column("posted_to_instagram_at")
        batch.drop_column("posted_to_facebook_at")
        batch.drop_column("notes")
        batch.drop_column("needs_review")
        batch.drop_column("review_reason")


def downgrade() -> None:
    with op.batch_alter_table("series") as batch:
        batch.add_column(sa.Column("scheduled_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("scheduled_targets", sa.Text(), nullable=False, server_default="[]")
        )
        batch.add_column(sa.Column("posted_to_telegram_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("posted_to_instagram_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("posted_to_facebook_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("review_reason", sa.String(), nullable=False, server_default=""))
