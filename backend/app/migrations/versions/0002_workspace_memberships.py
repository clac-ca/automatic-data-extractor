"""Add workspace and workspace_membership tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_workspace_memberships"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    workspace_role_enum = sa.Enum(
        "member",
        "owner",
        name="workspacerole",
        native_enum=False,
    )

    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_membership_id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("role", workspace_role_enum, nullable=False, server_default="member"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_membership_id"),
        sa.UniqueConstraint("user_id", "workspace_id"),
    )
    op.create_index(
        "workspace_memberships_user_id_idx",
        "workspace_memberships",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "workspace_memberships_user_id_idx", table_name="workspace_memberships"
    )
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
