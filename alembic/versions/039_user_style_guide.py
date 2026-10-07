"""user_settings.style_guide

Revision ID: 039
Revises: 038
Create Date: 2026-10-07
"""

import sqlalchemy as sa

from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(sa.Column("style_guide", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("style_guide")
