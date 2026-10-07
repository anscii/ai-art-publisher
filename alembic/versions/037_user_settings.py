"""user_settings: move per-user AI fields out of app_settings

Copies the Owner's (oldest admin's) AI keys/models into their user_settings row,
keys encrypted via app.crypto, then drops the 11 columns from app_settings.
openrouter_api_key stays on app_settings (Default AI Access key).

Downgrade re-adds the columns EMPTY: keys and model choices are not restored.

Revision ID: 037
Revises: 036
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from app.crypto import encrypt

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None

_KEYS = ["anthropic_api_key", "openai_api_key", "google_api_key", "deepseek_api_key"]
_MODELS = [
    "anthropic_default_model",
    "openai_default_model",
    "google_default_model",
    "deepseek_default_model",
    "openrouter_default_model",
    "image_edit_model",
]
_DROPPED = _KEYS + ["default_provider"] + _MODELS


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(), nullable=False),
        *[sa.Column(k, sa.Text(), nullable=False, server_default="") for k in _KEYS],
        sa.Column("openrouter_api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("default_provider", sa.String(), nullable=False, server_default="openrouter"),
        *[sa.Column(m, sa.String(), nullable=False, server_default="") for m in _MODELS],
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    cols = ", ".join(_DROPPED + ["openrouter_api_key"])
    row = bind.execute(text(f"SELECT {cols} FROM app_settings WHERE id = 1")).mappings().fetchone()
    admin = bind.execute(
        text("SELECT id FROM users WHERE is_admin = 1 ORDER BY created_at LIMIT 1")
    ).fetchone()
    if row:
        if admin:
            vals = {k: encrypt(row[k] or "") for k in _KEYS + ["openrouter_api_key"]}
            vals.update({k: row[k] or "" for k in _MODELS})
            vals["default_provider"] = row["default_provider"] or "openrouter"
            vals["user_id"] = admin[0]
            names = list(vals)
            bind.execute(
                text(
                    f"INSERT INTO user_settings ({', '.join(names)}) "
                    f"VALUES ({', '.join(':' + n for n in names)})"
                ),
                vals,
            )
        elif any(row[k] for k in _KEYS):
            raise RuntimeError("AI keys exist in app_settings but no admin user to own them.")

    with op.batch_alter_table("app_settings") as batch_op:
        for c in _DROPPED:
            batch_op.drop_column(c)


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        for c in _KEYS + _MODELS:
            batch_op.add_column(sa.Column(c, sa.String(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("default_provider", sa.String(), nullable=False, server_default="anthropic")
        )
    op.drop_table("user_settings")
