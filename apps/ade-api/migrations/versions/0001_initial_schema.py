"""Initial ADE schema with unified RBAC and run/build tracking.

This migration is designed to work across:
- SQLite
- PostgreSQL
- Microsoft SQL Server (via mssql+pyodbc)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# Revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Shared scalar types / enums
# ---------------------------------------------------------------------------

SCOPETYPE = sa.Enum(
    "global",
    "workspace",
    name="scopetype",
    native_enum=False,
    create_constraint=True,
    length=20,
)

PRINCIPALTYPE = sa.Enum(
    "user",
    name="principaltype",
    native_enum=False,
    create_constraint=True,
    length=20,
)

RUNSTATUS = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "canceled",
    name="run_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

BUILDSTATUS = sa.Enum(
    "queued",
    "building",
    "active",
    "failed",
    "canceled",
    name="api_build_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def _dialect_name() -> str:
    bind = op.get_bind()
    return bind.dialect.name


# ---------------------------------------------------------------------------
# Upgrade / downgrade entry points
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create initial ADE schema."""
    dialect = _dialect_name()

    _create_users()
    _create_user_credentials()
    _create_user_identities()
    _create_workspaces()
    _create_workspace_memberships()
    _create_permissions()
    _create_roles()
    _create_role_permissions()
    _create_principals()
    _create_role_assignments(dialect)
    _create_documents(dialect)
    _create_document_tags()
    _create_api_keys()
    _create_system_settings()
    _create_configurations()
    _create_runs(dialect)
    _create_run_logs()
    _create_builds(dialect)
    _create_build_logs()


def downgrade() -> None:  # pragma: no cover
    """Downgrade is not supported for the initial ADE schema."""
    raise NotImplementedError("Downgrade is not supported for this revision.")



# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_canonical", sa.String(length=320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "is_service_account",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )


def _create_user_credentials() -> None:
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_user_credentials_user_id",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("provider", "subject"),
    )
    op.create_index(
        "ix_user_identities_user_id",
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
        sa.Column(
            "settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "workspace_id"),
    )
    op.create_index(
        "ix_workspace_memberships_user_id",
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
        "ix_permissions_scope_type",
        "permissions",
        ["scope_type"],
        unique=False,
    )


def _create_roles() -> None:
    table = op.create_table(
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
        sa.Column(
            "built_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "editable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        "ix_roles_scope_lookup",
        "roles",
        ["scope_type", "scope_id"],
        unique=False,
    )

    # Unique "system" role slug per scope type where scope_id IS NULL.
    # Implemented as a partial/filtered unique index across dialects.
    op.create_index(
        "ux_roles_system_slug_scope_type",
        table.name,
        ["slug", "scope_type"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NULL"),
        sqlite_where=sa.text("scope_id IS NULL"),
        mssql_where=sa.text("scope_id IS NULL"),
    )


def _create_role_permissions() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("role_id", sa.String(length=26), nullable=False),
        sa.Column("permission_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("role_id", "permission_id"),
    )
    op.create_index(
        "ix_role_permissions_permission_id",
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
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(principal_type = 'user' AND user_id IS NOT NULL)",
            name="ck_principals_user_fk_required",
        ),
    )


def _create_role_assignments(dialect: str) -> None:
    # SQL Server does not allow multiple cascade paths. role_assignments already
    # cascades via role_id -> roles -> workspaces, so the direct FK from
    # scope_id to workspaces must *not* also cascade there.
    scope_ondelete: str | None = "CASCADE"
    if dialect == "mssql":
        scope_ondelete = None

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
            sa.ForeignKey("workspaces.id", ondelete=scope_ondelete),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("principal_id", "role_id", "scope_type", "scope_id"),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="ck_role_assignments_scope_consistency",
        ),
    )
    op.create_index(
        "ix_role_assignments_principal_scope",
        "role_assignments",
        ["principal_id", "scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_role_scope",
        "role_assignments",
        ["role_id", "scope_type", "scope_id"],
        unique=False,
    )


def _create_documents(dialect: str) -> None:
    # SQL Server again disallows multiple cascading paths. We prefer a single
    # SET NULL path from documents.deleted_by_user_id -> users, and leave
    # uploaded_by_user_id as a regular FK.
    uploaded_ondelete = "SET NULL"
    deleted_ondelete = "SET NULL"
    if dialect == "mssql":
        uploaded_ondelete = None

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column(
            "attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            ondelete=deleted_ondelete,
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            ondelete=uploaded_ondelete,
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','processing','processed','failed','archived')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint(
            "source IN ('manual_upload')",
            name="ck_documents_source",
        ),
    )
    op.create_index(
        "ix_documents_workspace_status_created",
        "documents",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_documents_workspace_status_created_live",
        "documents",
        ["workspace_id", "status", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
        mssql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_documents_workspace_created",
        "documents",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_documents_workspace_last_run",
        "documents",
        ["workspace_id", "last_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_documents_workspace_source",
        "documents",
        ["workspace_id", "source"],
        unique=False,
    )
    op.create_index(
        "ix_documents_workspace_uploader",
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("document_id", "tag"),
    )
    op.create_index(
        "ix_document_tags_document_id",
        "document_tags",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_tags_tag",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_api_keys_user_id",
        "api_keys",
        ["user_id"],
        unique=False,
    )


def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "value",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )


def _create_configurations() -> None:
    op.create_table(
        "configurations",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("content_digest", sa.String(length=80), nullable=True),
        sa.Column("active_build_id", sa.String(length=40), nullable=True),
        sa.Column("active_build_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_configurations_workspace_status",
        "configurations",
        ["workspace_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_configurations_active_build_id",
        "configurations",
        ["active_build_id"],
        unique=False,
    )


def _create_runs(dialect: str) -> None:
    workspace_ondelete: str | None = "CASCADE"
    input_doc_ondelete: str | None = "SET NULL"
    if dialect == "mssql":
        workspace_ondelete = None
        input_doc_ondelete = None

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("build_id", sa.String(length=40), nullable=True),
        sa.Column("status", RUNSTATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("retry_of_run_id", sa.String(length=40), nullable=True),
        sa.Column("input_document_id", sa.String(length=26), nullable=True),
        sa.Column("input_sheet_name", sa.String(length=64), nullable=True),
        sa.Column("input_sheet_names", sa.JSON(), nullable=True),
        sa.Column("input_documents", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("output_uri", sa.String(length=512), nullable=True),
        sa.Column("logs_uri", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_by_user_id", sa.String(length=26), nullable=True),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete=workspace_ondelete,
        ),
        sa.ForeignKeyConstraint(
            ["input_document_id"],
            ["documents.id"],
            ondelete=input_doc_ondelete,
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_runs_configuration",
        "runs",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        "ix_runs_workspace",
        "runs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_runs_status",
        "runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_runs_input_document",
        "runs",
        ["input_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_runs_workspace_input_finished",
        "runs",
        ["workspace_id", "input_document_id", "finished_at", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_runs_workspace_created",
        "runs",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_runs_retry_of",
        "runs",
        ["retry_of_run_id"],
        unique=False,
    )


def _create_run_logs() -> None:
    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "stream",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'stdout'"),
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_run_logs_run_id",
        "run_logs",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_run_logs_stream",
        "run_logs",
        ["stream"],
        unique=False,
    )


def _create_builds(dialect: str) -> None:
    workspace_ondelete: str | None = "CASCADE"
    if dialect == "mssql":
        workspace_ondelete = None

    op.create_table(
        "builds",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
        sa.Column("config_digest", sa.String(length=80), nullable=True),
        sa.Column("status", BUILDSTATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete=workspace_ondelete,
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["configurations.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_builds_workspace",
        "builds",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_builds_configuration",
        "builds",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        "ix_builds_status",
        "builds",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_builds_fingerprint",
        "builds",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        "ux_builds_inflight_per_config",
        "builds",
        ["configuration_id"],
        unique=True,
        postgresql_where=sa.text("status in ('queued','building')"),
        sqlite_where=sa.text("status in ('queued','building')"),
        mssql_where=sa.text("status in ('queued','building')"),
    )


def _create_build_logs() -> None:
    op.create_table(
        "build_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("build_id", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "stream",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'stdout'"),
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["builds.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_build_logs_build_id",
        "build_logs",
        ["build_id"],
        unique=False,
    )
    op.create_index(
        "ix_build_logs_stream",
        "build_logs",
        ["stream"],
        unique=False,
    )
