"""telegram stories: consolidate story/frame fields; add telegram MTProto settings

Revision ID: 029
Revises: 028
Create Date: 2026-06-03
"""

import sqlalchemy as sa

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # story_frames: add platform_frame_id, copy from instagram_frame_id, drop old cols
    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.add_column(sa.Column("platform_frame_id", sa.String(), nullable=True))

    op.execute(
        "UPDATE story_frames SET platform_frame_id = instagram_frame_id"
        " WHERE instagram_frame_id IS NOT NULL"
    )

    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.drop_column("instagram_frame_id")
        batch_op.drop_column("facebook_frame_id")

    # stories: add platform_result_json, copy from instagram_result_json, drop old cols
    with op.batch_alter_table("stories") as batch_op:
        batch_op.add_column(sa.Column("platform_result_json", sa.Text(), nullable=True))

    op.execute(
        "UPDATE stories SET platform_result_json = instagram_result_json"
        " WHERE instagram_result_json IS NOT NULL"
    )

    with op.batch_alter_table("stories") as batch_op:
        batch_op.drop_column("instagram_result_json")
        batch_op.drop_column("facebook_result_json")

    # app_settings: add Telegram MTProto credentials
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.add_column(
            sa.Column("telegram_api_id", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("telegram_api_hash", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("telegram_session_string", sa.Text(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.drop_column("telegram_session_string")
        batch_op.drop_column("telegram_api_hash")
        batch_op.drop_column("telegram_api_id")

    with op.batch_alter_table("stories") as batch_op:
        batch_op.add_column(sa.Column("instagram_result_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("facebook_result_json", sa.Text(), nullable=True))

    op.execute(
        "UPDATE stories SET instagram_result_json = platform_result_json"
        " WHERE platform_result_json IS NOT NULL"
    )

    with op.batch_alter_table("stories") as batch_op:
        batch_op.drop_column("platform_result_json")

    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.add_column(sa.Column("instagram_frame_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("facebook_frame_id", sa.String(), nullable=True))

    op.execute(
        "UPDATE story_frames SET instagram_frame_id = platform_frame_id"
        " WHERE platform_frame_id IS NOT NULL"
    )

    with op.batch_alter_table("story_frames") as batch_op:
        batch_op.drop_column("platform_frame_id")
