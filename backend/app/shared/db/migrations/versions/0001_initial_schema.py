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
    _create_configs()
    _create_config_versions()
    _create_config_files()
    _create_documents()
    _create_document_tags()
    _create_jobs(bind)
    _create_api_keys()
    _create_system_settings()


def downgrade() -> None:  # pragma: no cover - intentionally not implemented
    raise NotImplementedError("Downgrade is not supported for the initial schema.")


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
        sa.Column("role_id", sa.String(length=26), primary_key=True),
        sa.Column("scope_type", SCOPETYPE, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
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


def _create_principals() -> None:
    op.create_table(
        "principals",
        sa.Column("principal_id", sa.String(length=26), primary_key=True),
        sa.Column("principal_type", PRINCIPALTYPE, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=26),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
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
        sa.Column("assignment_id", sa.String(length=26), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(length=26),
            sa.ForeignKey("principals.principal_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=26),
            sa.ForeignKey("roles.role_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", SCOPETYPE, nullable=False),
        sa.Column(
            "scope_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
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
    op.create_index(
        "role_assignments_principal_role_idx",
        "role_assignments",
        ["principal_id", "role_id"],
        unique=False,
    )
def _create_configs() -> None:
    op.create_table(
        "configs",
        sa.Column("config_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.String(length=26), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("workspace_id", "slug"),
    )


def _create_config_versions() -> None:
    op.create_table(
        "config_versions",
        sa.Column("config_version_id", sa.String(length=26), primary_key=True),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("semver", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("files_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=26), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["config_id"], ["configs.config_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('active','inactive')",
            name="config_versions_status_ck",
        ),
    )
    op.create_index(
        "config_versions_active_unique_idx",
        "config_versions",
        ["config_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active' AND deleted_at IS NULL"),
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )


def _create_config_files() -> None:
    op.create_table(
        "config_files",
        sa.Column("config_file_id", sa.String(length=26), primary_key=True),
        sa.Column("config_version_id", sa.String(length=26), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column(
            "language",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'python'"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_versions.config_version_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("config_version_id", "path"),
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
        sa.Column("produced_by_job_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.user_id"], ondelete="SET NULL"
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
    op.create_index(
        "documents_produced_by_job_id_idx",
        "documents",
        ["produced_by_job_id"],
        unique=False,
    )


def _create_document_tags() -> None:
    op.create_table(
        "document_tags",
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "tag"),
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


def _create_jobs(bind: sa.engine.Connection) -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_version_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("input_document_id", sa.String(length=26), nullable=False),
        sa.Column("run_key", sa.String(length=64), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("logs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["config_version_id"],
            ["config_versions.config_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["input_document_id"], ["documents.document_id"], ondelete="RESTRICT"),
    )
    op.create_index("jobs_workspace_id_idx", "jobs", ["workspace_id"], unique=False)
    op.create_index("jobs_input_document_id_idx", "jobs", ["input_document_id"], unique=False)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documents") as batch_op:
            batch_op.create_foreign_key(
                "documents_produced_by_job_id_fkey",
                "jobs",
                ["produced_by_job_id"],
                ["job_id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "documents_produced_by_job_id_fkey",
            "documents",
            "jobs",
            ["produced_by_job_id"],
            ["job_id"],
            ondelete="SET NULL",
        )


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
