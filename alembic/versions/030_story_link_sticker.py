"""stories: add link_area_json for Telegram story link sticker placement

Revision ID: 030
Revises: 029
Create Date: 2026-06-04
"""

import sqlalchemy as sa

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stories") as batch_op:
        batch_op.add_column(sa.Column("link_area_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("stories") as batch_op:
        batch_op.drop_column("link_area_json")
