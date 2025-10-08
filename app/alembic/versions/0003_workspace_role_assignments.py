"""Introduce workspace-scoped role assignments via pivot table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_workspace_role_assignments"
down_revision = "0002_graph_rbac_scaffold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Introduce workspace-specific role scoping and membership pivots."""

    with op.batch_alter_table("roles") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "roles_workspace_id_fkey",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint("roles_slug_uniq", type_="unique")
        batch_op.create_unique_constraint(
            "roles_scope_workspace_slug_uniq",
            ["scope", "workspace_id", "slug"],
        )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "roles_system_slug_scope_uni",
            "roles",
            ["slug", "scope"],
            unique=True,
            postgresql_where=sa.text("workspace_id IS NULL"),
        )

    with op.batch_alter_table("workspace_memberships") as batch_op:
        batch_op.drop_column("role")
        batch_op.drop_column("role_id")

    op.create_table(
        "workspace_membership_roles",
        sa.Column(
            "workspace_membership_id",
            sa.String(length=26),
            sa.ForeignKey(
                "workspace_memberships.workspace_membership_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=26),
            sa.ForeignKey("roles.role_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("workspace_membership_id", "role_id"),
    )
    op.create_index(
        "workspace_membership_roles_role_id_idx",
        "workspace_membership_roles",
        ["role_id"],
        unique=False,
    )

    # Drop the legacy enumerated type generated for workspace roles if it exists.
    try:
        sa.Enum(name="workspacerole").drop(op.get_bind(), checkfirst=True)
    except Exception:
        # The dialect may have already removed the enum; ignore in that case.
        pass


def downgrade() -> None:
    """Revert workspace role scoping changes."""

    op.drop_index(
        "workspace_membership_roles_role_id_idx",
        table_name="workspace_membership_roles",
    )
    op.drop_table("workspace_membership_roles")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(
            "roles_system_slug_scope_uni",
            table_name="roles",
        )

    with op.batch_alter_table("roles") as batch_op:
        batch_op.drop_constraint("roles_scope_workspace_slug_uniq", type_="unique")
        batch_op.drop_constraint("roles_workspace_id_fkey", type_="foreignkey")
        batch_op.drop_column("workspace_id")
        batch_op.create_unique_constraint("roles_slug_uniq", ["slug"])

    with op.batch_alter_table("workspace_memberships") as batch_op:
        batch_op.add_column(
            sa.Column(
                "role_id",
                sa.String(length=26),
                sa.ForeignKey("roles.role_id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "role",
                sa.Enum(
                    "member",
                    "owner",
                    name="workspacerole",
                    native_enum=False,
                    length=20,
                ),
                nullable=False,
                server_default="member",
            )
        )

