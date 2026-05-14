"""add collections, posts, post_images; Series.name + collection_id

Revision ID: 007
Revises: 006
Create Date: 2026-05-14
"""

import json
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = set(inspector.get_table_names())
    series_cols = {c["name"] for c in inspector.get_columns("series")}

    if "collections" not in existing_tables:
        op.create_table(
            "collections",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )

    if "posts" not in existing_tables:
        op.create_table(
            "posts",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "series_id",
                sa.String(),
                sa.ForeignKey("series.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("platform", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("external_post_id", sa.String(), nullable=True),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )

    if "post_images" not in existing_tables:
        op.create_table(
            "post_images",
            sa.Column(
                "post_id",
                sa.String(),
                sa.ForeignKey("posts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "image_id",
                sa.String(),
                sa.ForeignKey("images.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("post_id", "image_id"),
        )

    if "name" not in series_cols:
        op.add_column("series", sa.Column("name", sa.String(), nullable=False, server_default=""))

    if "collection_id" not in series_cols:
        op.add_column("series", sa.Column("collection_id", sa.String(), nullable=True))

    # Data: copy title → name for rows where name is still empty
    bind.execute(text("UPDATE series SET name = title WHERE name = '' OR name IS NULL"))

    # Data: migrate existing posted/scheduled Series → Post records
    # Only if the old posting columns still exist on series
    series_cols_now = {c["name"] for c in inspector.get_columns("series")}
    has_old_cols = "posted_to_telegram_at" in series_cols_now

    if has_old_cols:
        now = datetime.utcnow().isoformat()
        rows = bind.execute(
            text(
                "SELECT id, title, description_en, description_ru, "
                "tags_instagram, tags_telegram, status, "
                "scheduled_at, scheduled_targets, "
                "posted_to_telegram_at, posted_to_instagram_at, posted_to_facebook_at "
                "FROM series WHERE deleted_at IS NULL"
            )
        ).fetchall()

        for row in rows:
            (
                series_id,
                title,
                desc_en,
                desc_ru,
                tags_ig,
                tags_tg,
                status,
                sched_at,
                sched_targets,
                ptg,
                pig,
                pfb,
            ) = row

            def _make_post(platform, description, tags_json, post_status, scheduled_at, posted_at):
                bind.execute(
                    text(
                        "INSERT INTO posts (id, series_id, platform, title, description, tags, "
                        "status, scheduled_at, posted_at, error_message, created_at) "
                        "VALUES (:id, :sid, :platform, :title, :desc, :tags, "
                        ":status, :sched, :posted, :error_message, :created)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "sid": series_id,
                        "platform": platform,
                        "title": title or "",
                        "desc": description or "",
                        "tags": tags_json or "[]",
                        "status": post_status,
                        "sched": scheduled_at,
                        "posted": posted_at,
                        "error_message": "",
                        "created": now,
                    },
                )

            if status == "scheduled" and sched_at:
                targets = []
                try:
                    targets = json.loads(sched_targets or "[]")
                except Exception:
                    targets = ["telegram", "instagram"]
                for platform in targets:
                    desc = desc_ru if platform == "telegram" else desc_en
                    tags = tags_tg if platform == "telegram" else tags_ig
                    _make_post(platform, desc, tags, "scheduled", sched_at, None)

            if ptg:
                _make_post("telegram", desc_ru, tags_tg, "posted", None, ptg)
            if pig:
                _make_post("instagram", desc_en, tags_ig, "posted", None, pig)
            if pfb:
                _make_post("facebook", desc_en, tags_ig, "posted", None, pfb)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = set(inspector.get_table_names())
    series_cols = {c["name"] for c in inspector.get_columns("series")}

    if "collection_id" in series_cols:
        op.drop_column("series", "collection_id")
    if "name" in series_cols:
        op.drop_column("series", "name")
    if "post_images" in existing_tables:
        op.drop_table("post_images")
    if "posts" in existing_tables:
        op.drop_table("posts")
    if "collections" in existing_tables:
        op.drop_table("collections")
