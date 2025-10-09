"""Initial ADE schema with Graph-style RBAC."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

PERMISSION_SCOPE = sa.Enum(
    "global", "workspace", name="permissionscope", native_enum=False, length=20
)
ROLE_SCOPE = sa.Enum("global", "workspace", name="rolescope", native_enum=False, length=20)


def upgrade() -> None:
    _create_users()
    _create_user_credentials()
    _create_user_identities()
    _create_workspaces()
    _create_workspace_memberships()
    _create_permissions()
    _create_roles()
    _create_role_permissions()
    _create_user_global_roles()
    _create_workspace_membership_roles()
    _create_configurations()
    _create_documents()
    _create_jobs()
    _create_api_keys()
    _create_system_settings()


def downgrade() -> None:  # pragma: no cover - exercised in migration tests
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("roles_system_slug_scope_uni", table_name="roles")

    op.drop_table("system_settings")
    op.drop_table("api_keys")
    op.drop_table("jobs")
    op.drop_table("documents")
    op.drop_table("configurations")
    op.drop_table("workspace_membership_roles")
    op.drop_table("user_global_roles")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("user_identities")
    op.drop_table("user_credentials")
    op.drop_table("users")

    # Drop Enum types for databases that materialise them (e.g., PostgreSQL)
    try:
        PERMISSION_SCOPE.drop(bind, checkfirst=False)
    except NotImplementedError:
        pass
    try:
        ROLE_SCOPE.drop(bind, checkfirst=False)
    except NotImplementedError:
        pass


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_canonical", sa.String(length=320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_user_credentials() -> None:
    op.create_table(
        "user_credentials",
        sa.Column("credential_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "user_credentials_user_id_idx",
        "user_credentials",
        ["user_id"],
        unique=False,
    )


def _create_user_identities() -> None:
    op.create_table(
        "user_identities",
        sa.Column("identity_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "subject"),
    )
    op.create_index(
        "user_identities_user_id_idx",
        "user_identities",
        ["user_id"],
        unique=False,
    )


def _create_workspaces() -> None:
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_membership_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "workspace_id"),
    )
    op.create_index(
        "workspace_memberships_user_id_idx",
        "workspace_memberships",
        ["user_id"],
        unique=False,
    )


def _create_permissions() -> None:
    op.create_table(
        "permissions",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("scope", PERMISSION_SCOPE, nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("permissions_scope_idx", "permissions", ["scope"], unique=False)


def _create_roles() -> None:
    op.create_table(
        "roles",
        sa.Column("role_id", sa.String(length=26), primary_key=True),
        sa.Column("scope", ROLE_SCOPE, nullable=False),
        sa.Column(
            "workspace_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slug", sa.String(length=100), nullable=False),
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
        sa.UniqueConstraint("scope", "workspace_id", "slug", name="roles_scope_workspace_slug_uniq"),
    )
    op.create_index("roles_scope_idx", "roles", ["scope"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "roles_system_slug_scope_uni",
            "roles",
            ["slug", "scope"],
            unique=True,
            postgresql_where=sa.text("workspace_id IS NULL"),
        )


def _create_role_permissions() -> None:
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            sa.String(length=26),
            sa.ForeignKey("roles.role_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_key",
            sa.String(length=120),
            sa.ForeignKey("permissions.key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_key"),
    )
    op.create_index(
        "role_permissions_permission_key_idx",
        "role_permissions",
        ["permission_key"],
        unique=False,
    )


def _create_user_global_roles() -> None:
    op.create_table(
        "user_global_roles",
        sa.Column(
            "user_id",
            sa.String(length=26),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=26),
            sa.ForeignKey("roles.role_id", ondelete="CASCADE"),
            nullable=False,
        ),
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


def _create_workspace_membership_roles() -> None:
    op.create_table(
        "workspace_membership_roles",
        sa.Column(
            "workspace_membership_id",
            sa.String(length=26),
            sa.ForeignKey("workspace_memberships.workspace_membership_id", ondelete="CASCADE"),
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


def _create_configurations() -> None:
    op.create_table(
        "configurations",
        sa.Column("configuration_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "document_type", "version"),
    )
    op.create_index(
        "configurations_workspace_active_idx",
        "configurations",
        ["workspace_id", "document_type"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
    )


def _create_documents() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("produced_by_job_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
    )
    op.create_index(
        "documents_workspace_id_idx",
        "documents",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "documents_produced_by_job_id_idx",
        "documents",
        ["produced_by_job_id"],
        unique=False,
    )


def _create_jobs() -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("input_document_id", sa.String(length=26), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("logs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["configuration_id"], ["configurations.configuration_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["input_document_id"], ["documents.document_id"], ondelete="RESTRICT"),
    )
    op.create_index("jobs_workspace_id_idx", "jobs", ["workspace_id"], unique=False)
    op.create_index("jobs_input_document_id_idx", "jobs", ["input_document_id"], unique=False)


def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        sa.Column("api_key_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_ip", sa.String(length=45), nullable=True),
        sa.Column("last_seen_user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )
    op.create_index("api_keys_user_id_idx", "api_keys", ["user_id"], unique=False)


def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
