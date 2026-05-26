"""add sending to post status values

Revision ID: 022
Revises: 021
Create Date: 2026-05-26
"""

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Post.status is a plain String column in SQLite with no CHECK constraint.
    # No schema change required — this migration documents the new "sending"
    # status value added for async background posting.
    pass


def downgrade() -> None:
    pass
