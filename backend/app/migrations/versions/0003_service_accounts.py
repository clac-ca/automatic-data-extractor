"""Introduce service accounts and flexible API key principals."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_service_accounts"
down_revision = "0002_workspace_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_accounts",
        sa.Column("service_account_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("service_account_id"),
        sa.UniqueConstraint("name"),
    )

    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.add_column(sa.Column("service_account_id", sa.String(length=26), nullable=True))
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(length=26),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "api_keys_service_account_id_fkey",
            "service_accounts",
            ["service_account_id"],
            ["service_account_id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "api_keys_service_account_id_idx",
            ["service_account_id"],
            unique=False,
        )
        batch_op.create_check_constraint(
            "api_keys_principal_check",
            "(user_id IS NOT NULL AND service_account_id IS NULL)"
            " OR (user_id IS NULL AND service_account_id IS NOT NULL)",
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM api_keys WHERE service_account_id IS NOT NULL")
    )
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.drop_constraint("api_keys_principal_check", type_="check")
        batch_op.drop_index("api_keys_service_account_id_idx")
        batch_op.drop_constraint("api_keys_service_account_id_fkey", type_="foreignkey")
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(length=26),
            nullable=False,
        )
        batch_op.drop_column("service_account_id")
    op.drop_table("service_accounts")
