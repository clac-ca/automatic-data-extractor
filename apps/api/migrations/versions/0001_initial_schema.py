"""Initial ADE schema with unified RBAC."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

SCOPETYPE = sa.Enum(
    "global",
    "workspace",
    name="scopetype",
    native_enum=False,
    length=20,
)

PRINCIPALTYPE = sa.Enum(
    "user",
    name="principaltype",
    native_enum=False,
    length=20,
)

JOBSTATUS = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="jobstatus",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    bind = op.get_bind()

    _create_users()
    _create_user_credentials()
    _create_user_identities()
    _create_workspaces()
    _create_workspace_memberships()
    _create_permissions()
    _create_roles(bind)
    _create_role_permissions()
    _create_principals()
    _create_role_assignments()
    _create_documents()
    _create_document_tags()
    _create_api_keys()
    _create_system_settings()
    _create_configs()
    _create_config_versions()
    _create_workspace_config_states()
    _create_configurations()
    _create_configuration_builds()
    _create_jobs()


def downgrade() -> None:  # pragma: no cover - intentionally not implemented
    raise NotImplementedError("Downgrade is not supported for the initial schema.")


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=26), primary_key=True),
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
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
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
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
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
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
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
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("resource", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("scope_type", SCOPETYPE, nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index(
        "permissions_scope_type_idx",
        "permissions",
        ["scope_type"],
        unique=False,
    )


def _create_roles(bind: sa.engine.Connection) -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("scope_type", SCOPETYPE, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("built_in", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.UniqueConstraint("scope_type", "scope_id", "slug"),
    )
    op.create_index(
        "roles_scope_lookup_idx",
        "roles",
        ["scope_type", "scope_id"],
        unique=False,
    )
    if bind.dialect.name == "postgresql":
        op.create_index(
            "roles_system_slug_scope_type_uni",
            "roles",
            ["slug", "scope_type"],
            unique=True,
            postgresql_where=sa.text("scope_id IS NULL"),
        )
    elif bind.dialect.name == "sqlite":
        op.create_index(
            "roles_system_slug_scope_type_uni",
            "roles",
            ["slug", "scope_type"],
            unique=True,
            sqlite_where=sa.text("scope_id IS NULL"),
        )


def _create_role_permissions() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("role_id", sa.String(length=26), nullable=False),
        sa.Column("permission_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_id"),
    )
    op.create_index(
        "role_permissions_permission_id_idx",
        "role_permissions",
        ["permission_id"],
        unique=False,
    )


def _create_principals() -> None:
    op.create_table(
        "principals",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("principal_type", PRINCIPALTYPE, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(principal_type = 'user' AND user_id IS NOT NULL)",
            name="principals_user_fk_required",
        ),
    )


def _create_role_assignments() -> None:
    op.create_table(
        "role_assignments",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(length=26),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=26),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", SCOPETYPE, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("principal_id", "role_id", "scope_type", "scope_id"),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR"
            " (scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="role_assignments_scope_consistency",
        ),
    )
    op.create_index(
        "role_assignments_principal_scope_idx",
        "role_assignments",
        ["principal_id", "scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "role_assignments_role_scope_idx",
        "role_assignments",
        ["role_id", "scope_type", "scope_id"],
        unique=False,
    )
def _create_documents() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("uploaded_by_user_id", sa.String(length=26), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'uploaded'"),
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'manual_upload'"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','processing','processed','failed','archived')",
            name="documents_status_ck",
        ),
        sa.CheckConstraint(
            "source IN ('manual_upload')",
            name="documents_source_ck",
        ),
    )
    op.create_index(
        "documents_workspace_status_created_idx",
        "documents",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "documents_workspace_created_idx",
        "documents",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "documents_workspace_last_run_idx",
        "documents",
        ["workspace_id", "last_run_at"],
        unique=False,
    )
    op.create_index(
        "documents_workspace_source_idx",
        "documents",
        ["workspace_id", "source"],
        unique=False,
    )
    op.create_index(
        "documents_workspace_uploader_idx",
        "documents",
        ["workspace_id", "uploaded_by_user_id"],
        unique=False,
    )


def _create_document_tags() -> None:
    op.create_table(
        "document_tags",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "tag"),
    )
    op.create_index(
        "document_tags_document_id_idx",
        "document_tags",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "document_tags_tag_idx",
        "document_tags",
        ["tag"],
        unique=False,
    )
def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=26), primary_key=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("api_keys_user_id_idx", "api_keys", ["user_id"], unique=False)


def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_configs() -> None:
    op.create_table(
        "configs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("workspace_id", "slug"),
    )
    op.create_index("configs_workspace_idx", "configs", ["workspace_id"], unique=False)
    op.create_index(
        "configs_workspace_deleted_idx",
        "configs",
        ["workspace_id", "deleted_at"],
        unique=False,
    )


def _create_config_versions() -> None:
    op.create_table(
        "config_versions",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("package_path", sa.String(length=512), nullable=False),
        sa.Column("config_script_api_version", sa.String(length=10), nullable=False, server_default=sa.text("'1'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["configs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("config_id", "sequence"),
    )
    op.create_index(
        "config_versions_config_idx",
        "config_versions",
        ["config_id"],
        unique=False,
    )
    op.create_index(
        "config_versions_deleted_idx",
        "config_versions",
        ["config_id", "deleted_at"],
        unique=False,
    )


def _create_workspace_config_states() -> None:
    op.create_table(
        "workspace_config_states",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=True),
        sa.Column("config_version_id", sa.String(length=26), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["configs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("workspace_id"),
        sa.UniqueConstraint("config_version_id"),
    )
    op.create_index(
        "workspace_config_states_workspace_idx",
        "workspace_config_states",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "workspace_config_states_active_version_idx",
        "workspace_config_states",
        ["config_version_id"],
        unique=False,
    )


def _create_configurations() -> None:
    op.create_table(
        "configurations",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "config_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("content_digest", sa.String(length=80), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "config_id"),
    )
    op.create_index(
        "configurations_workspace_status_idx",
        "configurations",
        ["workspace_id", "status"],
        unique=False,
    )
    op.create_index(
        "configurations_workspace_active_unique",
        "configurations",
        ["workspace_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def _create_configuration_builds() -> None:
    op.create_table(
        "configuration_builds",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("build_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("venv_path", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=True),
        sa.Column("content_digest", sa.String(length=128), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["configurations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "config_id", "build_id"),
        sa.CheckConstraint(
            "status in ('building','active','inactive','failed')",
            name="configuration_builds_status_check",
        ),
    )
    op.create_index(
        "configuration_builds_active_idx",
        "configuration_builds",
        ["configuration_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "configuration_builds_building_idx",
        "configuration_builds",
        ["configuration_id"],
        unique=True,
        sqlite_where=sa.text("status = 'building'"),
        postgresql_where=sa.text("status = 'building'"),
    )


def _create_jobs() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("config_version_id", sa.String(length=26), nullable=False),
        sa.Column("submitted_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("status", JOBSTATUS, nullable=False, server_default=sa.text("'queued'")),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("retry_of_job_id", sa.String(length=26), nullable=True),
        sa.Column("input_hash", sa.String(length=128), nullable=True),
        sa.Column("input_documents", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("output_uri", sa.String(length=512), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("logs_uri", sa.String(length=512), nullable=True),
        sa.Column("run_request_uri", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["configs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("jobs_workspace_idx", "jobs", ["workspace_id", "created_at"], unique=False)
    op.create_index(
        "jobs_config_version_idx",
        "jobs",
        ["config_version_id"],
        unique=False,
    )
    op.create_index(
        "jobs_input_idx",
        "jobs",
        ["workspace_id", "config_version_id", "input_hash"],
        unique=False,
    )
    op.create_index(
        "jobs_status_queued_idx",
        "jobs",
        ["status", "queued_at"],
        unique=False,
    )
    op.create_index(
        "jobs_retry_of_idx",
        "jobs",
        ["retry_of_job_id"],
        unique=False,
    )
    op.create_index(
        "jobs_input_unique_idx",
        "jobs",
        ["workspace_id", "config_version_id", "input_hash"],
        unique=True,
        sqlite_where=sa.text("retry_of_job_id IS NULL"),
        postgresql_where=sa.text("retry_of_job_id IS NULL"),
    )
