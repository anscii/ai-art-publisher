"""add indexes on FK and frequently-filtered columns

Revision ID: 020
Revises: 019
Create Date: 2026-05-20
"""

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_series_status", "series", ["status"])
    op.create_index("ix_series_collection_id", "series", ["collection_id"])
    op.create_index("ix_series_deleted_at", "series", ["deleted_at"])
    op.create_index("ix_images_series_id", "images", ["series_id"])
    op.create_index("ix_images_status", "images", ["status"])
    op.create_index("ix_images_deleted_at", "images", ["deleted_at"])
    op.create_index("ix_posts_series_id", "posts", ["series_id"])
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_scheduled_at", "posts", ["scheduled_at"])
    op.create_index("ix_ai_variants_series_id", "ai_variants", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_variants_series_id", "ai_variants")
    op.drop_index("ix_posts_scheduled_at", "posts")
    op.drop_index("ix_posts_status", "posts")
    op.drop_index("ix_posts_series_id", "posts")
    op.drop_index("ix_images_deleted_at", "images")
    op.drop_index("ix_images_status", "images")
    op.drop_index("ix_images_series_id", "images")
    op.drop_index("ix_series_deleted_at", "series")
    op.drop_index("ix_series_collection_id", "series")
    op.drop_index("ix_series_status", "series")
