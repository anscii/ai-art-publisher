"""app_settings: add image_edit_model

Revision ID: 032
Revises: 031
Create Date: 2026-10-02
"""

import sqlalchemy as sa

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.add_column(
            sa.Column("image_edit_model", sa.String(), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.drop_column("image_edit_model")
