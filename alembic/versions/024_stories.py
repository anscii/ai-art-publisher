"""add stories and story_frames tables

Revision ID: 024
Revises: 023
Create Date: 2026-05-28
"""

import sqlalchemy as sa

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if "stories" not in existing:
        op.create_table(
            "stories",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("post_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("rendered_at", sa.DateTime(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("instagram_result_json", sa.Text(), nullable=True),
            sa.Column("facebook_result_json", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id"),
        )
        op.create_index("ix_stories_post_id", "stories", ["post_id"])

    if "story_frames" not in existing:
        op.create_table(
            "story_frames",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("story_id", sa.String(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("frame_type", sa.String(), nullable=False),
            sa.Column("source_image_id", sa.String(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column(
                "background_mode", sa.String(), nullable=False, server_default="image_blur_dim"
            ),
            sa.Column("rendered_url", sa.String(), nullable=True),
            sa.Column("rendered_storage_key", sa.String(), nullable=True),
            sa.Column("instagram_frame_id", sa.String(), nullable=True),
            sa.Column("facebook_frame_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_image_id"], ["images.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_story_frames_story_id", "story_frames", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_story_frames_story_id", table_name="story_frames")
    op.drop_table("story_frames")
    op.drop_index("ix_stories_post_id", table_name="stories")
    op.drop_table("stories")
