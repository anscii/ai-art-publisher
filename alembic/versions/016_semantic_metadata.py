"""add semantic metadata fields to ai_variants and posts

Revision ID: 016
Revises: 015
Create Date: 2026-05-15
"""

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_variants", sa.Column("instagram_seo", sa.Text(), nullable=True))
    op.add_column("ai_variants", sa.Column("pinterest_title", sa.Text(), nullable=True))
    op.add_column("ai_variants", sa.Column("pinterest_description", sa.Text(), nullable=True))
    op.add_column("ai_variants", sa.Column("pinterest_board", sa.Text(), nullable=True))
    op.add_column("ai_variants", sa.Column("archive_metadata", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("seo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "seo")
    op.drop_column("ai_variants", "archive_metadata")
    op.drop_column("ai_variants", "pinterest_board")
    op.drop_column("ai_variants", "pinterest_description")
    op.drop_column("ai_variants", "pinterest_title")
    op.drop_column("ai_variants", "instagram_seo")
