"""Initial ADE schema with UUID primary keys and simplified RBAC.

Designed for UUIDv7 identifiers generated in the application layer using
:func:`ade_api.common.ids.generate_uuid7` (RFC 9562).
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
# Types / enums
# ---------------------------------------------------------------------------


class UUIDType(TypeDecorator):
    """Platform-agnostic UUID storage.

    Uses native UUID types on PostgreSQL and SQL Server; falls back to a
    36-character string representation elsewhere. Values are always returned
    to Python as uuid.UUID objects.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        name = dialect.name
        if name in {"postgresql", "postgres"}:
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        if name == "mssql":
            from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        # Fallback: store as a 36-character string
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        # Accept strings or other UUID-like values
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


def _dialect_name() -> Optional[str]:
    """Return the current dialect name if available (handles offline mode)."""

    try:
        bind = op.get_bind()
    except Exception:
        # In Alembic offline mode there may be no bind at all
        return None

    if bind is None:
        return None

    return bind.dialect.name


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """Common created_at / updated_at pair."""
    return (
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


RUN_STATUS = sa.Enum(
    "queued",
    "waiting_for_build",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="run_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

BUILD_STATUS = sa.Enum(
    "queued",
    "building",
    "ready",
    "failed",
    "cancelled",
    name="build_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

CONFIG_STATUS = sa.Enum(
    "draft",
    "published",
    "active",
    "inactive",
    name="configuration_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

DOCUMENT_STATUS = sa.Enum(
    "uploaded",
    "processing",
    "processed",
    "failed",
    "archived",
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

PERMISSION_SCOPE = sa.Enum(
    "global",
    "workspace",
    name="permission_scope",
    native_enum=False,
    create_constraint=True,
    length=20,
)

RBAC_SCOPE = sa.Enum(
    "global",
    "workspace",
    name="rbac_scope",
    native_enum=False,
    create_constraint=True,
    length=20,
)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # Identity & auth
    _create_users()
    _create_user_credentials()
    _create_user_identities()
    _create_workspaces()
    _create_workspace_memberships()

    # RBAC
    _create_permissions()
    _create_roles()
    _create_role_permissions()
    _create_user_role_assignments()
    _create_api_keys()

    # Settings / configuration / builds
    _create_system_settings()
    _create_configurations()
    _create_builds()

    # Content
    _create_documents()
    _create_document_tags()

    # Runtime
    _create_runs()


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrade is not supported for this revision.")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _uuid_pk(name: str = "id") -> sa.Column:
    """UUID primary key column.

    There is intentionally *no* server-side default here. IDs are expected
    to be generated in the application layer as UUIDv7 identifiers (RFC 9562).
    """
    return sa.Column(
        name,
        UUIDType(),
        primary_key=True,
        nullable=False,
    )


def _create_users() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column(
            "email_canonical",
            sa.String(length=320),
            nullable=False,
            unique=True,
        ),
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
        *_timestamps(),
    )


def _create_user_credentials() -> None:
    op.create_table(
        "user_credentials",
        _uuid_pk(),
        sa.Column(
            "user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", name="uq_user_credentials_user"),
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
        _uuid_pk(),
        sa.Column(
            "user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "provider",
            "subject",
            name="uq_user_identities_provider_subject",
        ),
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
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        *_timestamps(),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column(
            "user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            primary_key=True,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_workspace_memberships_user_id",
        "workspace_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
        unique=False,
    )


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
    op.create_index(
        "ix_permissions_scope_type",
        "permissions",
        ["scope_type"],
        unique=False,
    )


def _create_roles() -> None:
    op.create_table(
        "roles",
        _uuid_pk(),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_editable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        *_timestamps(),
        sa.Column(
            "created_by_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_roles_slug",
        "roles",
        ["slug"],
        unique=False,
    )


def _create_role_permissions() -> None:
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            UUIDType(),
            sa.ForeignKey("roles.id", ondelete="NO ACTION"),
            primary_key=True,
        ),
        sa.Column(
            "permission_id",
            UUIDType(),
            sa.ForeignKey("permissions.id", ondelete="NO ACTION"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_role_permissions_permission_id",
        "role_permissions",
        ["permission_id"],
        unique=False,
    )


def _create_user_role_assignments() -> None:
    op.create_table(
        "user_role_assignments",
        _uuid_pk(),
        sa.Column(
            "user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            UUIDType(),
            sa.ForeignKey("roles.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("scope_type", RBAC_SCOPE, nullable=False),
        sa.Column(
            "scope_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="chk_user_role_scope",
        ),
        sa.UniqueConstraint(
            "user_id",
            "role_id",
            "scope_type",
            "scope_id",
            name="uq_user_role_scope",
        ),
    )
    op.create_index(
        "ix_user_scope",
        "user_role_assignments",
        ["user_id", "scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_scope",
        "user_role_assignments",
        ["role_id", "scope_type", "scope_id"],
        unique=False,
    )


def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        _uuid_pk(),
        sa.Column(
            "owner_user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("scope_type", RBAC_SCOPE, nullable=False, server_default="global"),
        sa.Column(
            "scope_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("token_prefix", sa.String(length=32), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(length=45), nullable=True),
        sa.Column("last_used_user_agent", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="chk_api_key_scope",
        ),
    )
    op.create_index(
        "ix_api_keys_owner_scope",
        "api_keys",
        ["owner_user_id", "scope_type", "scope_id"],
        unique=False,
    )


def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column(
            "value",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        *_timestamps(),
    )


def _create_configurations() -> None:
    op.create_table(
        "configurations",
        _uuid_pk(),
        sa.Column(
            "workspace_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", CONFIG_STATUS, nullable=False, server_default="draft"),
        sa.Column("content_digest", sa.String(length=80), nullable=True),
        sa.Column("active_build_id", UUIDType(), nullable=True),
        sa.Column("active_build_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
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


def _create_builds() -> None:
    dialect = _dialect_name()

    op.create_table(
        "builds",
        _uuid_pk(),
        sa.Column(
            "workspace_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column(
            "configuration_id",
            UUIDType(),
            sa.ForeignKey("configurations.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
        sa.Column("config_digest", sa.String(length=80), nullable=True),
        sa.Column("status", BUILD_STATUS, nullable=False, server_default="queued"),
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
    )
    op.create_index("ix_builds_workspace", "builds", ["workspace_id"], unique=False)
    op.create_index(
        "ix_builds_configuration",
        "builds",
        ["configuration_id"],
        unique=False,
    )
    op.create_index("ix_builds_status", "builds", ["status"], unique=False)
    op.create_index("ix_builds_fingerprint", "builds", ["fingerprint"], unique=False)

    # At most one queued/building build per configuration where the dialect supports
    # partial/filtered indexes. On others, keep a non-unique index instead.
    inflight_where = sa.text("status in ('queued','building')")

    if dialect in {"postgresql", "postgres"}:
        op.create_index(
            "ux_builds_inflight_per_config",
            "builds",
            ["configuration_id"],
            unique=True,
            postgresql_where=inflight_where,
        )
    elif dialect == "sqlite":
        op.create_index(
            "ux_builds_inflight_per_config",
            "builds",
            ["configuration_id"],
            unique=True,
            sqlite_where=inflight_where,
        )
    elif dialect == "mssql":
        op.create_index(
            "ux_builds_inflight_per_config",
            "builds",
            ["configuration_id"],
            unique=True,
            mssql_where=inflight_where,
        )
    else:
        op.create_index(
            "ix_builds_inflight_per_config",
            "builds",
            ["configuration_id"],
            unique=False,
        )

    # Foreign key from configurations.active_build_id → builds.id
    # Skipped on SQLite due to ALTER TABLE limitations and on MSSQL to avoid
    # multiple cascade path errors stemming from workspace-level cascades.
    if dialect not in {"sqlite", "mssql"}:
        op.create_foreign_key(
            "fk_configurations_active_build_id",
            source_table="configurations",
            referent_table="builds",
            local_cols=["active_build_id"],
            remote_cols=["id"],
            ondelete="NO ACTION",
        )


def _create_runs() -> None:
    op.create_table(
        "runs",
        _uuid_pk(),
        sa.Column(
            "configuration_id",
            UUIDType(),
            sa.ForeignKey("configurations.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column(
            "build_id",
            UUIDType(),
            sa.ForeignKey("builds.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column(
            "input_document_id",
            UUIDType(),
            sa.ForeignKey("documents.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("input_sheet_names", sa.JSON(), nullable=True),
        sa.Column("status", RUN_STATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "retry_of_run_id",
            UUIDType(),
            sa.ForeignKey("runs.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("submitted_by_user_id", UUIDType(), nullable=True),
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
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            ondelete="NO ACTION",
        ),
    )
    op.create_index("ix_runs_configuration", "runs", ["configuration_id"], unique=False)
    op.create_index("ix_runs_workspace", "runs", ["workspace_id"], unique=False)
    op.create_index("ix_runs_status", "runs", ["status"], unique=False)
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
    op.create_index("ix_runs_retry_of", "runs", ["retry_of_run_id"], unique=False)
    op.create_index("ix_runs_build", "runs", ["build_id"], unique=False)


def _create_documents() -> None:
    dialect = _dialect_name()

    op.create_table(
        "documents",
        _uuid_pk(),
        sa.Column(
            "workspace_id",
            UUIDType(),
            sa.ForeignKey("workspaces.id", ondelete="NO ACTION"),
            nullable=False,
        ),
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
        sa.Column(
            "uploaded_by_user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("status", DOCUMENT_STATUS, nullable=False, server_default="uploaded"),
        sa.Column(
            "source",
            DOCUMENT_SOURCE,
            nullable=False,
            server_default="manual_upload",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by_user_id",
            UUIDType(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_documents_workspace_status_created",
        "documents",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )

    live_where = sa.text("deleted_at IS NULL")

    if dialect in {"postgresql", "postgres"}:
        op.create_index(
            "ix_documents_workspace_status_created_live",
            "documents",
            ["workspace_id", "status", "created_at"],
            unique=False,
            postgresql_where=live_where,
        )
    elif dialect == "sqlite":
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
    else:
        op.create_index(
            "ix_documents_workspace_status_created_live",
            "documents",
            ["workspace_id", "status", "created_at"],
            unique=False,
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
        sa.Column(
            "document_id",
            UUIDType(),
            sa.ForeignKey("documents.id", ondelete="NO ACTION"),
            primary_key=True,
        ),
        sa.Column("tag", sa.String(length=100), primary_key=True, nullable=False),
    )
    op.create_index(
        "ix_document_tags_document_id",
        "document_tags",
        ["document_id"],
        unique=False,
    )
    op.create_index("ix_document_tags_tag", "document_tags", ["tag"], unique=False)
