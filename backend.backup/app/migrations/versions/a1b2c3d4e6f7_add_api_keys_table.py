"""Add hashed API keys table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e6f7"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("api_key_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.String(length=32), nullable=True),
        sa.Column("last_seen_ip", sa.String(length=45), nullable=True),
        sa.Column("last_seen_user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_prefix"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
