"""Initial ADE schema (SQLite + SQL Server only).

Notes:
- GUID primary keys are app-generated (no server default).
- SQLite: uses constraints-based enums.
- SQL Server: uses NVARCHAR + CHECK constraints for enums (via native_enum=False).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import CHAR, TypeDecorator

# Revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision: Optional[str] = None
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class GUID(TypeDecorator):
    """SQLite + SQL Server GUID storage."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "mssql":
            from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    @property
    def python_type(self) -> type[uuid.UUID]:
        return uuid.UUID


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _uuid_pk(name: str = "id") -> sa.Column:
    return sa.Column(name, GUID(), primary_key=True, nullable=False)


def _dialect_name() -> Optional[str]:
    try:
        bind = op.get_bind()
    except Exception:
        return None
    return bind.dialect.name if bind is not None else None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

RUN_STATUS = sa.Enum(
    "queued", "running", "succeeded", "failed", "cancelled",
    name="run_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

BUILD_STATUS = sa.Enum(
    "queued", "building", "ready", "failed", "cancelled",
    name="build_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

CONFIG_STATUS = sa.Enum(
    "draft", "active", "archived",
    name="configuration_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

DOCUMENT_STATUS = sa.Enum(
    "uploaded", "processing", "processed", "failed", "archived",
    name="document_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

DOCUMENT_SOURCE = sa.Enum(
    "manual_upload",
    name="document_source",
    native_enum=False,
    create_constraint=True,
    length=50,
)

DOCUMENT_CHANGE_TYPE = sa.Enum(
    "upsert", "deleted",
    name="document_change_type",
    native_enum=False,
    create_constraint=True,
    length=20,
)

DOCUMENT_UPLOAD_CONFLICT_BEHAVIOR = sa.Enum(
    "rename", "replace", "fail",
    name="document_upload_conflict_behavior",
    native_enum=False,
    create_constraint=True,
    length=20,
)

DOCUMENT_UPLOAD_SESSION_STATUS = sa.Enum(
    "active", "complete", "committed", "cancelled",
    name="document_upload_session_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

PERMISSION_SCOPE = sa.Enum(
    "global", "workspace",
    name="permission_scope",
    native_enum=False,
    create_constraint=True,
    length=20,
)


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    _create_users()
    _create_oauth_accounts()
    _create_access_tokens()
    _create_workspaces()
    _create_workspace_memberships()

    _create_permissions()
    _create_roles()
    _create_role_permissions()
    _create_user_role_assignments()
    _create_api_keys()

    _create_system_settings()
    _create_configurations()
    _create_builds()

    _create_documents()
    _create_document_tags()
    _create_document_changes()
    _create_document_upload_sessions()

    _create_runs()
    _create_run_metrics()
    _create_run_fields()
    _create_run_table_columns()

    _create_idempotency_keys()


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _create_users() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("email_normalized", sa.String(length=320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )


def _create_oauth_accounts() -> None:
    op.create_table(
        "oauth_accounts",
        _uuid_pk(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("oauth_name", sa.String(length=100), nullable=False),
        sa.Column("account_id", sa.String(length=255), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("oauth_name", "account_id", name="uq_oauth_accounts_name_account"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"], unique=False)


def _create_access_tokens() -> None:
    op.create_table(
        "access_tokens",
        _uuid_pk(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_access_tokens_user_id", "access_tokens", ["user_id"], unique=False)


def _create_workspaces() -> None:
    op.create_table(
        "workspaces",
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), primary_key=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"], unique=False)
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"], unique=False)


def _create_permissions() -> None:
    op.create_table(
        "permissions",
        _uuid_pk(),
        sa.Column("key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("resource", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("scope_type", PERMISSION_SCOPE, nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_permissions_scope_type", "permissions", ["scope_type"], unique=False)


def _create_roles() -> None:
    op.create_table(
        "roles",
        _uuid_pk(),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.Column("created_by_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("updated_by_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
    )
    op.create_index("ix_roles_slug", "roles", ["slug"], unique=False)


def _create_role_permissions() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="NO ACTION"), primary_key=True),
        sa.Column("permission_id", GUID(), sa.ForeignKey("permissions.id", ondelete="NO ACTION"), primary_key=True),
    )
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"], unique=False)


def _create_user_role_assignments() -> None:
    op.create_table(
        "user_role_assignments",
        _uuid_pk(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "role_id", "workspace_id", name="uq_user_role_assignment_scope"),
    )
    op.create_index("ix_user_role_assignments_user_id", "user_role_assignments", ["user_id"], unique=False)
    op.create_index("ix_user_role_assignments_workspace_id", "user_role_assignments", ["workspace_id"], unique=False)


def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        _uuid_pk(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("prefix", sa.String(length=32), nullable=False, unique=True),
        sa.Column("hashed_secret", sa.String(length=128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)


def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
    )


def _create_configurations() -> None:
    dialect = _dialect_name()

    op.create_table(
        "configurations",
        _uuid_pk(),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", CONFIG_STATUS, nullable=False, server_default="draft"),
        sa.Column("content_digest", sa.String(length=80), nullable=True),
        sa.Column("active_build_id", GUID(), nullable=True),
        sa.Column("active_build_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_configurations_workspace_status", "configurations", ["workspace_id", "status"], unique=False)
    op.create_index("ix_configurations_active_build_id", "configurations", ["active_build_id"], unique=False)

    # One active configuration per workspace using partial/filtered unique index
    active_where = sa.text("status = 'active'")
    if dialect == "sqlite":
        op.create_index(
            "ux_configurations_active_per_workspace",
            "configurations",
            ["workspace_id"],
            unique=True,
            sqlite_where=active_where,
        )
    elif dialect == "mssql":
        op.create_index(
            "ux_configurations_active_per_workspace",
            "configurations",
            ["workspace_id"],
            unique=True,
            mssql_where=active_where,
        )
    else:
        op.create_index("ix_configurations_active_per_workspace", "configurations", ["workspace_id"], unique=False)


def _create_builds() -> None:
    dialect = _dialect_name()

    op.create_table(
        "builds",
        _uuid_pk(),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("configuration_id", GUID(), sa.ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
        sa.Column("config_digest", sa.String(length=80), nullable=True),
        sa.Column("status", BUILD_STATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("configuration_id", "fingerprint", name="ux_builds_config_fingerprint"),
    )
    op.create_index("ix_builds_workspace", "builds", ["workspace_id"], unique=False)
    op.create_index("ix_builds_configuration", "builds", ["configuration_id"], unique=False)
    op.create_index("ix_builds_status", "builds", ["status"], unique=False)
    op.create_index("ix_builds_fingerprint", "builds", ["fingerprint"], unique=False)

    # Optional FK configurations.active_build_id -> builds.id skipped on sqlite+mssql
    if dialect not in {"sqlite", "mssql"}:
        op.create_foreign_key(
            "fk_configurations_active_build_id",
            source_table="configurations",
            referent_table="builds",
            local_cols=["active_build_id"],
            remote_cols=["id"],
            ondelete="NO ACTION",
        )


def _create_documents() -> None:
    dialect = _dialect_name()

    op.create_table(
        "documents",
        _uuid_pk(),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("uploaded_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("assignee_user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("status", DOCUMENT_STATUS, nullable=False, server_default="uploaded"),
        sa.Column("source", DOCUMENT_SOURCE, nullable=False, server_default="manual_upload"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
        *_timestamps(),
    )

    op.create_index(
        "ix_documents_workspace_status_created",
        "documents",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )

    # Live (non-deleted) index with sqlite/mssql partial where
    live_where = sa.text("deleted_at IS NULL")
    if dialect == "sqlite":
        op.create_index(
            "ix_documents_workspace_status_created_live",
            "documents",
            ["workspace_id", "status", "created_at"],
            unique=False,
            sqlite_where=live_where,
        )
    elif dialect == "mssql":
        op.create_index(
            "ix_documents_workspace_status_created_live",
            "documents",
            ["workspace_id", "status", "created_at"],
            unique=False,
            mssql_where=live_where,
        )

    op.create_index("ix_documents_workspace_created", "documents", ["workspace_id", "created_at"], unique=False)
    op.create_index("ix_documents_workspace_last_run", "documents", ["workspace_id", "last_run_at"], unique=False)
    op.create_index("ix_documents_workspace_source", "documents", ["workspace_id", "source"], unique=False)
    op.create_index("ix_documents_workspace_uploader", "documents", ["workspace_id", "uploaded_by_user_id"], unique=False)
    op.create_index("ix_documents_workspace_assignee", "documents", ["workspace_id", "assignee_user_id"], unique=False)


def _create_document_tags() -> None:
    op.create_table(
        "document_tags",
        _uuid_pk(),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("document_id", "tag", name="document_tags_document_id_tag_key"),
    )
    op.create_index("ix_document_tags_document_id", "document_tags", ["document_id"], unique=False)
    op.create_index("ix_document_tags_tag", "document_tags", ["tag"], unique=False)
    op.create_index("document_tags_tag_document_id_idx", "document_tags", ["tag", "document_id"], unique=False)


def _create_document_changes() -> None:
    op.create_table(
        "document_changes",
        sa.Column(
            "cursor",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("type", DOCUMENT_CHANGE_TYPE, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_changes_workspace_cursor", "document_changes", ["workspace_id", "cursor"], unique=False)
    op.create_index("ix_document_changes_workspace_document", "document_changes", ["workspace_id", "document_id"], unique=False)
    op.create_index("ix_document_changes_workspace_occurred", "document_changes", ["workspace_id", "occurred_at"], unique=False)


def _create_document_upload_sessions() -> None:
    op.create_table(
        "document_upload_sessions",
        _uuid_pk(),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("conflict_behavior", DOCUMENT_UPLOAD_CONFLICT_BEHAVIOR, nullable=False, server_default="rename"),
        sa.Column("folder_id", sa.String(length=255), nullable=True),
        sa.Column("temp_stored_uri", sa.String(length=512), nullable=False),
        sa.Column("received_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received_ranges", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", DOCUMENT_UPLOAD_SESSION_STATUS, nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_document_upload_sessions_workspace", "document_upload_sessions", ["workspace_id"], unique=False)
    op.create_index("ix_document_upload_sessions_expires", "document_upload_sessions", ["expires_at"], unique=False)
    op.create_index("ix_document_upload_sessions_status", "document_upload_sessions", ["status"], unique=False)


def _create_runs() -> None:
    dialect = _dialect_name()

    op.create_table(
        "runs",
        _uuid_pk(),
        sa.Column("configuration_id", GUID(), sa.ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("build_id", GUID(), sa.ForeignKey("builds.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("input_document_id", GUID(), sa.ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("input_sheet_names", sa.JSON(), nullable=True),
        sa.Column("output_path", sa.String(length=512), nullable=True),
        sa.Column("status", RUN_STATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("submitted_by_user_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),

        # Durable queue fields (from your old 0002)
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_options", sa.JSON(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("claimed_by", sa.String(length=255), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="NO ACTION"),
    )

    op.create_index("ix_runs_configuration", "runs", ["configuration_id"], unique=False)
    op.create_index("ix_runs_workspace", "runs", ["workspace_id"], unique=False)
    op.create_index("ix_runs_status", "runs", ["status"], unique=False)
    op.create_index("ix_runs_input_document", "runs", ["input_document_id"], unique=False)
    op.create_index("ix_runs_workspace_input_finished", "runs", ["workspace_id", "input_document_id", "completed_at", "started_at"], unique=False)
    op.create_index("ix_runs_workspace_created", "runs", ["workspace_id", "created_at"], unique=False)
    op.create_index("ix_runs_build", "runs", ["build_id"], unique=False)

    # Claim/queue index
    op.create_index("ix_runs_claim", "runs", ["status", "available_at", "created_at"], unique=False)

    # Unique "active job" per document/config/workspace for queued/running
    active_where = sa.text("status IN ('queued','running')")
    if dialect == "sqlite":
        op.create_index(
            "uq_runs_active_job",
            "runs",
            ["workspace_id", "input_document_id", "configuration_id"],
            unique=True,
            sqlite_where=active_where,
        )
    elif dialect == "mssql":
        op.create_index(
            "uq_runs_active_job",
            "runs",
            ["workspace_id", "input_document_id", "configuration_id"],
            unique=True,
            mssql_where=active_where,
        )
    else:
        op.create_index(
            "ix_runs_active_job",
            "runs",
            ["workspace_id", "input_document_id", "configuration_id"],
            unique=False,
        )


def _create_run_metrics() -> None:
    op.create_table(
        "run_metrics",
        sa.Column("run_id", GUID(), sa.ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True, nullable=False),
        sa.Column("evaluation_outcome", sa.String(length=20), nullable=True),
        sa.Column("evaluation_findings_total", sa.Integer(), nullable=True),
        sa.Column("evaluation_findings_info", sa.Integer(), nullable=True),
        sa.Column("evaluation_findings_warning", sa.Integer(), nullable=True),
        sa.Column("evaluation_findings_error", sa.Integer(), nullable=True),
        sa.Column("validation_issues_total", sa.Integer(), nullable=True),
        sa.Column("validation_issues_info", sa.Integer(), nullable=True),
        sa.Column("validation_issues_warning", sa.Integer(), nullable=True),
        sa.Column("validation_issues_error", sa.Integer(), nullable=True),
        sa.Column("validation_max_severity", sa.String(length=10), nullable=True),
        sa.Column("workbook_count", sa.Integer(), nullable=True),
        sa.Column("sheet_count", sa.Integer(), nullable=True),
        sa.Column("table_count", sa.Integer(), nullable=True),
        sa.Column("row_count_total", sa.Integer(), nullable=True),
        sa.Column("row_count_empty", sa.Integer(), nullable=True),
        sa.Column("column_count_total", sa.Integer(), nullable=True),
        sa.Column("column_count_empty", sa.Integer(), nullable=True),
        sa.Column("column_count_mapped", sa.Integer(), nullable=True),
        sa.Column("column_count_unmapped", sa.Integer(), nullable=True),
        sa.Column("field_count_expected", sa.Integer(), nullable=True),
        sa.Column("field_count_detected", sa.Integer(), nullable=True),
        sa.Column("field_count_not_detected", sa.Integer(), nullable=True),
        sa.Column("cell_count_total", sa.Integer(), nullable=True),
        sa.Column("cell_count_non_empty", sa.Integer(), nullable=True),
    )


def _create_run_fields() -> None:
    op.create_table(
        "run_fields",
        sa.Column("run_id", GUID(), sa.ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True, nullable=False),
        sa.Column("field", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("detected", sa.Boolean(), nullable=False),
        sa.Column("best_mapping_score", sa.Float(), nullable=True),
        sa.Column("occurrences_tables", sa.Integer(), nullable=False),
        sa.Column("occurrences_columns", sa.Integer(), nullable=False),
    )
    op.create_index("ix_run_fields_run", "run_fields", ["run_id"], unique=False)
    op.create_index("ix_run_fields_field", "run_fields", ["field"], unique=False)


def _create_run_table_columns() -> None:
    op.create_table(
        "run_table_columns",
        sa.Column("run_id", GUID(), sa.ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True, nullable=False),
        sa.Column("workbook_index", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workbook_name", sa.String(length=255), nullable=False),
        sa.Column("sheet_index", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("table_index", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("column_index", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("header_raw", sa.Text(), nullable=True),
        sa.Column("header_normalized", sa.Text(), nullable=True),
        sa.Column("non_empty_cells", sa.Integer(), nullable=False),
        sa.Column("mapping_status", sa.String(length=32), nullable=False),
        sa.Column("mapped_field", sa.String(length=128), nullable=True),
        sa.Column("mapping_score", sa.Float(), nullable=True),
        sa.Column("mapping_method", sa.String(length=32), nullable=True),
        sa.Column("unmapped_reason", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_run_table_columns_run", "run_table_columns", ["run_id"], unique=False)
    op.create_index("ix_run_table_columns_run_sheet", "run_table_columns", ["run_id", "sheet_name"], unique=False)
    op.create_index("ix_run_table_columns_run_mapped_field", "run_table_columns", ["run_id", "mapped_field"], unique=False)


def _create_idempotency_keys() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", "scope_key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_expires_at", "idempotency_keys", ["expires_at"], unique=False)
