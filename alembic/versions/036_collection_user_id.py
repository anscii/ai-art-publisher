"""collections: add user_id, backfill onto the oldest admin

Revision ID: 036
Revises: 035
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("collections") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))

    # Every pre-036 collection is the Owner's; 035 guarantees an admin exists.
    admin_row = bind.execute(
        text("SELECT id FROM users WHERE is_admin = 1 ORDER BY created_at LIMIT 1")
    ).fetchone()
    if admin_row:
        bind.execute(text("UPDATE collections SET user_id = :uid"), {"uid": admin_row[0]})
    elif bind.execute(text("SELECT 1 FROM collections LIMIT 1")).fetchone():
        raise RuntimeError("Collections exist but no admin user to assign them to.")

    with op.batch_alter_table("collections") as batch_op:
        batch_op.alter_column("user_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_collections_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_collections_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("collections") as batch_op:
        batch_op.drop_index("ix_collections_user_id")
        batch_op.drop_constraint("fk_collections_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
