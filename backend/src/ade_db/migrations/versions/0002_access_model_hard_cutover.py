"""Access model hard-cutover schema additions.

Adds principal-aware role assignments, groups, invitations, and extended user
profile fields while preserving legacy tables for runtime compatibility during
the cutover.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_access_model_hard_cutover"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    principal_type = sa.Enum(
        "user",
        "group",
        name="principal_type",
        native_enum=False,
    )
    assignment_scope_type = sa.Enum(
        "organization",
        "workspace",
        name="assignment_scope_type",
        native_enum=False,
    )
    group_membership_mode = sa.Enum(
        "assigned",
        "dynamic",
        name="group_membership_mode",
        native_enum=False,
    )
    group_source = sa.Enum(
        "internal",
        "idp",
        name="group_source",
        native_enum=False,
    )
    invitation_status = sa.Enum(
        "pending",
        "accepted",
        "expired",
        "cancelled",
        name="invitation_status",
        native_enum=False,
    )

    bind = op.get_bind()
    principal_type.create(bind, checkfirst=True)
    assignment_scope_type.create(bind, checkfirst=True)
    group_membership_mode.create(bind, checkfirst=True)
    group_source.create(bind, checkfirst=True)
    invitation_status.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("given_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("surname", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("office_location", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("mobile_phone", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("business_phones", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("employee_id", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("employee_type", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("preferred_language", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("state", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(length=120), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'internal'"),
        ),
    )
    op.add_column("users", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_users_source_external_not_null",
        "users",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "groups",
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "membership_mode",
            group_membership_mode,
            nullable=False,
            server_default="assigned",
        ),
        sa.Column(
            "source",
            group_source,
            nullable=False,
            server_default="internal",
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_groups")),
        sa.UniqueConstraint("slug", name=op.f("uq_groups_slug")),
        sa.CheckConstraint(
            "membership_mode in ('assigned', 'dynamic')",
            name="ck_groups_membership_mode",
        ),
        sa.CheckConstraint(
            "source in ('internal', 'idp')",
            name="ck_groups_source",
        ),
    )
    op.create_index("ix_groups_slug", "groups", ["slug"], unique=False)
    op.create_index("ix_groups_source", "groups", ["source"], unique=False)
    op.create_index("ix_groups_external_id", "groups", ["external_id"], unique=False)
    op.create_index(
        "uq_groups_source_external_not_null",
        "groups",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "group_memberships",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "membership_source",
            sa.String(length=20),
            nullable=False,
            server_default="internal",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group_memberships")),
        sa.UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_group_memberships_group_user",
        ),
    )
    op.create_index(
        "ix_group_memberships_group_id",
        "group_memberships",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        "ix_group_memberships_user_id",
        "group_memberships",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "role_assignments",
        sa.Column("principal_type", principal_type, nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("scope_type", assignment_scope_type, nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["scope_id"], ["workspaces.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignments")),
        sa.UniqueConstraint(
            "principal_type",
            "principal_id",
            "role_id",
            "scope_type",
            "scope_id",
            name="uq_role_assignments_principal_role_scope",
        ),
        sa.CheckConstraint(
            "(scope_type = 'organization' AND scope_id IS NULL) "
            "OR (scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="ck_role_assignments_scope_consistency",
        ),
        sa.CheckConstraint(
            "principal_type in ('user', 'group')",
            name="ck_role_assignments_principal_type",
        ),
        sa.CheckConstraint(
            "scope_type in ('organization', 'workspace')",
            name="ck_role_assignments_scope_type",
        ),
    )
    op.create_index(
        "ix_role_assignments_principal",
        "role_assignments",
        ["principal_type", "principal_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_scope",
        "role_assignments",
        ["scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_role_id",
        "role_assignments",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "uq_role_assignments_org_principal_role",
        "role_assignments",
        ["principal_type", "principal_id", "role_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'organization' AND scope_id IS NULL"),
    )
    op.create_index(
        "uq_role_assignments_workspace_principal_role_scope",
        "role_assignments",
        ["principal_type", "principal_id", "role_id", "scope_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'workspace' AND scope_id IS NOT NULL"),
    )

    op.create_table(
        "invitations",
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("invited_user_id", sa.UUID(), nullable=True),
        sa.Column("invited_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            invitation_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invited_user_id"], ["users.id"], ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.CheckConstraint(
            "status in ('pending', 'accepted', 'expired', 'cancelled')",
            name="ck_invitations_status",
        ),
    )
    op.create_index(
        "ix_invitations_email_normalized",
        "invitations",
        ["email_normalized"],
        unique=False,
    )
    op.create_index("ix_invitations_status", "invitations", ["status"], unique=False)
    op.create_index(
        "ix_invitations_invited_user_id",
        "invitations",
        ["invited_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_invitations_invited_by_user_id",
        "invitations",
        ["invited_by_user_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO role_assignments (
            principal_type,
            principal_id,
            role_id,
            scope_type,
            scope_id,
            created_at,
            updated_at
        )
        SELECT
            'user' AS principal_type,
            user_id AS principal_id,
            role_id,
            CASE
                WHEN workspace_id IS NULL THEN 'organization'
                ELSE 'workspace'
            END AS scope_type,
            workspace_id AS scope_id,
            created_at,
            updated_at
        FROM user_role_assignments
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY principal_type, principal_id, role_id, scope_type, scope_id
                    ORDER BY created_at, id
                ) AS rn
            FROM role_assignments
        )
        DELETE FROM role_assignments
        WHERE id IN (
            SELECT id
            FROM ranked
            WHERE rn > 1
        )
        """
    )

    legacy_distinct_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT DISTINCT user_id, role_id, workspace_id
                FROM user_role_assignments
            ) AS legacy_distinct
            """
        )
    ).scalar_one()
    mirrored_count = bind.execute(
        sa.text("SELECT count(*) FROM role_assignments WHERE principal_type = 'user'")
    ).scalar_one()
    if mirrored_count < legacy_distinct_count:
        raise RuntimeError(
            "role_assignments backfill failed parity check: "
            f"legacy_distinct={legacy_distinct_count}, mirrored={mirrored_count}"
        )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
