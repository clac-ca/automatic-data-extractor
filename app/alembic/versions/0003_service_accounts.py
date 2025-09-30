"""Augment users with service-account metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_service_accounts"
down_revision = "0002_workspace_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("display_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("description", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_service_account",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("created_by_user_id", sa.String(length=26), nullable=True)
        )
        batch_op.create_foreign_key(
            "users_created_by_user_id_fkey",
            "users",
            ["created_by_user_id"],
            ["user_id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "users_is_service_account_idx",
        "users",
        ["is_service_account"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("users_is_service_account_idx", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("users_created_by_user_id_fkey", type_="foreignkey")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("is_service_account")
        batch_op.drop_column("description")
        batch_op.drop_column("display_name")
