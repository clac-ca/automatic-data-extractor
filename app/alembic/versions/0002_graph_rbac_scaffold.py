"""Introduce Graph-style RBAC tables and seed definitions (draft)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_graph_rbac_scaffold"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


PERMISSION_SCOPE = sa.Enum("global", "workspace", name="permissionscope", native_enum=False)
ROLE_SCOPE = sa.Enum("global", "workspace", name="rolescope", native_enum=False)


def upgrade() -> None:
    """Create registry tables for the new RBAC model."""

    op.create_table(
        "permissions",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("scope", PERMISSION_SCOPE, nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("permissions_scope_idx", "permissions", ["scope"], unique=False)

    op.create_table(
        "roles",
        sa.Column("role_id", sa.String(length=26), primary_key=True),
        sa.Column("scope", ROLE_SCOPE, nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("editable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(length=26), nullable=True),
        sa.Column("updated_by", sa.String(length=26), nullable=True),
    )
    op.create_index("roles_scope_idx", "roles", ["scope"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=26), sa.ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_key", sa.String(length=120), sa.ForeignKey("permissions.key", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_key"),
    )
    op.create_index(
        "role_permissions_permission_key_idx",
        "role_permissions",
        ["permission_key"],
        unique=False,
    )

    op.create_table(
        "user_global_roles",
        sa.Column("user_id", sa.String(length=26), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(length=26), sa.ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index(
        "user_global_roles_user_id_idx",
        "user_global_roles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "user_global_roles_role_id_idx",
        "user_global_roles",
        ["role_id"],
        unique=False,
    )

    with op.batch_alter_table("workspace_memberships") as batch_op:
        batch_op.drop_column("permissions")
        batch_op.add_column(
            sa.Column(
                "role_id",
                sa.String(length=26),
                sa.ForeignKey("roles.role_id", ondelete="SET NULL"),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Drop RBAC tables (non-destructive draft)."""

    with op.batch_alter_table("workspace_memberships") as batch_op:
        batch_op.drop_column("role_id")
        batch_op.add_column(
            sa.Column(
                "permissions",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
    op.drop_index("user_global_roles_role_id_idx", table_name="user_global_roles")
    op.drop_index("user_global_roles_user_id_idx", table_name="user_global_roles")
    op.drop_table("user_global_roles")
    op.drop_index("role_permissions_permission_key_idx", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("roles_scope_idx", table_name="roles")
    op.drop_table("roles")
    op.drop_index("permissions_scope_idx", table_name="permissions")
    op.drop_table("permissions")

    PERMISSION_SCOPE.drop(op.get_bind(), checkfirst=False)
    ROLE_SCOPE.drop(op.get_bind(), checkfirst=False)
