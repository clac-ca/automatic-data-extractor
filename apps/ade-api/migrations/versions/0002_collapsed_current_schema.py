"""Collapse migrations 0002-0008 into a single upgrade from 0001.

Assumes the database is exactly at 0001_initial_schema.
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

from ade_api.db import GUID

# Revision identifiers, used by Alembic.
revision = "0002_collapsed_current_schema"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


DOCUMENT_INDEXES = [
    "ix_documents_workspace_status_created",
    "ix_documents_workspace_status_created_live",
    "ix_documents_workspace_last_run",
]

LEGACY_DOCUMENT_EVENT_COLUMNS = ("request_id", "client_request_id", "payload")


SSO_PROVIDER_STATUS = sa.Enum(
    "active",
    "disabled",
    "deleted",
    name="sso_provider_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

SSO_PROVIDER_TYPE = sa.Enum(
    "oidc",
    name="sso_provider_type",
    native_enum=False,
    create_constraint=True,
    length=20,
)

SSO_PROVIDER_MANAGED_BY = sa.Enum(
    "db",
    "env",
    name="sso_provider_managed_by",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    inspector = sa.inspect(bind)
    try:
        columns = [col["name"] for col in inspector.get_columns(table)]
    except Exception:
        return False
    return column in columns


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    inspector = sa.inspect(bind)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def _drop_mssql_indexes() -> None:
    for index in DOCUMENT_INDEXES:
        op.execute(
            f"""
            IF EXISTS (
                SELECT 1
                FROM sys.indexes
                WHERE name = '{index}'
                  AND object_id = OBJECT_ID('dbo.documents')
            )
            DROP INDEX {index} ON dbo.documents;
            """
        )


def _drop_mssql_document_status_constraint() -> None:
    op.execute(
        """
        DECLARE @constraint_name NVARCHAR(255);
        SELECT @constraint_name = dc.name
        FROM sys.check_constraints AS dc
        INNER JOIN sys.columns AS c
            ON dc.parent_object_id = c.object_id
            AND dc.parent_column_id = c.column_id
        WHERE dc.parent_object_id = OBJECT_ID('dbo.documents')
          AND c.name = 'status';
        IF @constraint_name IS NOT NULL
            EXEC('ALTER TABLE dbo.documents DROP CONSTRAINT ' + @constraint_name);
        """
    )


def _drop_mssql_default_constraint(*, table: str, column: str) -> None:
    op.execute(
        f"""
        DECLARE @constraint_name NVARCHAR(255);
        SELECT @constraint_name = dc.name
        FROM sys.default_constraints AS dc
        INNER JOIN sys.columns AS c
            ON dc.parent_object_id = c.object_id
            AND dc.parent_column_id = c.column_id
        WHERE dc.parent_object_id = OBJECT_ID('dbo.{table}')
          AND c.name = '{column}';
        IF @constraint_name IS NOT NULL
            EXEC('ALTER TABLE dbo.{table} DROP CONSTRAINT ' + @constraint_name);
        """
    )


def _ensure_mssql_alembic_version_length() -> None:
    op.execute(
        """
        IF EXISTS (
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'alembic_version'
              AND COLUMN_NAME = 'version_num'
              AND CHARACTER_MAXIMUM_LENGTH BETWEEN 1 AND 63
        )
        BEGIN
            ALTER TABLE alembic_version ALTER COLUMN version_num VARCHAR(128) NOT NULL;
        END;
        """
    )


def _drop_document_event_legacy_columns_mssql() -> None:
    for name in LEGACY_DOCUMENT_EVENT_COLUMNS:
        if _column_exists("document_events", name):
            op.drop_column("document_events", name)


def _drop_mssql_document_event_triggers() -> None:
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_documents_events_insert', 'TR') IS NOT NULL
            DROP TRIGGER dbo.trg_documents_events_insert;
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_documents_events_update', 'TR') IS NOT NULL
            DROP TRIGGER dbo.trg_documents_events_update;
        """
    )


def _create_mssql_document_event_triggers() -> None:
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_documents_events_insert', 'TR') IS NULL
        EXEC('
        CREATE TRIGGER dbo.trg_documents_events_insert
        ON dbo.documents
        AFTER INSERT
        AS
        BEGIN
            SET NOCOUNT ON;
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            SELECT
                i.workspace_id,
                i.id,
                ''document.changed'',
                i.version,
                i.updated_at
            FROM inserted AS i;
        END;
        ');
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_documents_events_update', 'TR') IS NULL
        EXEC('
        CREATE TRIGGER dbo.trg_documents_events_update
        ON dbo.documents
        AFTER UPDATE
        AS
        BEGIN
            SET NOCOUNT ON;
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            SELECT
                i.workspace_id,
                i.id,
                CASE
                    WHEN i.deleted_at IS NOT NULL AND d.deleted_at IS NULL
                        THEN ''document.deleted''
                    ELSE ''document.changed''
                END,
                i.version,
                i.updated_at
            FROM inserted AS i
            INNER JOIN deleted AS d ON d.id = i.id
            WHERE i.version <> d.version;
        END;
        ');
        """
    )


def _drop_mssql_run_env_triggers() -> None:
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_runs_events_insert', 'TR') IS NOT NULL
            DROP TRIGGER dbo.trg_runs_events_insert;
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_runs_events_update', 'TR') IS NOT NULL
            DROP TRIGGER dbo.trg_runs_events_update;
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_environments_events_update', 'TR') IS NOT NULL
            DROP TRIGGER dbo.trg_environments_events_update;
        """
    )


def _create_run_env_triggers_mssql() -> None:
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_runs_events_insert', 'TR') IS NULL
        EXEC('
        CREATE TRIGGER dbo.trg_runs_events_insert
        ON dbo.runs
        AFTER INSERT
        AS
        BEGIN
            SET NOCOUNT ON;
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            SELECT
                i.workspace_id,
                i.input_document_id,
                ''document.changed'',
                d.version,
                ISNULL(i.created_at, SYSUTCDATETIME())
            FROM inserted AS i
            INNER JOIN documents AS d ON d.id = i.input_document_id
            WHERE i.input_document_id IS NOT NULL;
        END;
        ');
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_runs_events_update', 'TR') IS NULL
        EXEC('
        CREATE TRIGGER dbo.trg_runs_events_update
        ON dbo.runs
        AFTER UPDATE
        AS
        BEGIN
            SET NOCOUNT ON;
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            SELECT
                i.workspace_id,
                i.input_document_id,
                ''document.changed'',
                d.version,
                SYSUTCDATETIME()
            FROM inserted AS i
            INNER JOIN deleted AS d_old ON d_old.id = i.id
            INNER JOIN documents AS d ON d.id = i.input_document_id
            WHERE i.input_document_id IS NOT NULL
              AND (
                i.status <> d_old.status
                OR i.started_at <> d_old.started_at
                OR i.completed_at <> d_old.completed_at
                OR i.output_path <> d_old.output_path
                OR i.error_message <> d_old.error_message
              );
        END;
        ');
        """
    )
    op.execute(
        """
        IF OBJECT_ID('dbo.trg_environments_events_update', 'TR') IS NULL
        EXEC('
        CREATE TRIGGER dbo.trg_environments_events_update
        ON dbo.environments
        AFTER UPDATE
        AS
        BEGIN
            SET NOCOUNT ON;
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            SELECT
                doc.workspace_id,
                doc.id,
                ''document.changed'',
                doc.version,
                SYSUTCDATETIME()
            FROM inserted AS i
            INNER JOIN deleted AS d_old ON d_old.id = i.id
            INNER JOIN runs AS r
                ON r.workspace_id = i.workspace_id
                AND r.configuration_id = i.configuration_id
                AND r.engine_spec = i.engine_spec
                AND r.deps_digest = i.deps_digest
            INNER JOIN documents AS doc ON doc.last_run_id = r.id
            WHERE (
                (d_old.status = ''ready'' AND i.status <> ''ready'')
                OR (d_old.status <> ''ready'' AND i.status = ''ready'')
            )
              AND r.status = ''queued'';
        END;
        ');
        """
    )


def _backfill_last_run_id_mssql() -> None:
    op.execute(
        """
        UPDATE documents
        SET last_run_id = latest.id
        FROM documents
        OUTER APPLY (
            SELECT TOP (1) id
            FROM runs
            WHERE runs.input_document_id = documents.id
            ORDER BY runs.created_at DESC, runs.id DESC
        ) AS latest
        WHERE documents.last_run_id IS NULL;
        """
    )


def _backfill_comment_count() -> None:
    op.execute(
        """
        UPDATE documents
        SET comment_count = (
            SELECT COUNT(*)
            FROM document_comments
            WHERE document_comments.document_id = documents.id
        );
        """
    )


def _create_document_comments_tables() -> None:
    if _table_exists("document_comments"):
        return
    op.create_table(
        "document_comments",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("author_user_id", GUID(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_comments_document_created",
        "document_comments",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_comments_workspace_created",
        "document_comments",
        ["workspace_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "document_comment_mentions",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "comment_id",
            GUID(),
            sa.ForeignKey("document_comments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mentioned_user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="document_comment_mentions_comment_user_key",
        ),
    )
    op.create_index(
        "ix_document_comment_mentions_comment",
        "document_comment_mentions",
        ["comment_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_comment_mentions_user",
        "document_comment_mentions",
        ["mentioned_user_id"],
        unique=False,
    )


def _create_sso_tables() -> None:
    if _table_exists("sso_providers"):
        return
    op.create_table(
        "sso_providers",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("type", SSO_PROVIDER_TYPE, nullable=False, server_default="oidc"),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_enc", sa.Text(), nullable=False),
        sa.Column("status", SSO_PROVIDER_STATUS, nullable=False, server_default="disabled"),
        sa.Column("managed_by", SSO_PROVIDER_MANAGED_BY, nullable=False, server_default="db"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sso_providers_status", "sso_providers", ["status"], unique=False)
    op.create_index("ix_sso_providers_issuer", "sso_providers", ["issuer"], unique=False)

    op.create_table(
        "sso_provider_domains",
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("domain", name="uq_sso_provider_domains_domain"),
    )
    op.create_index(
        "ix_sso_provider_domains_domain",
        "sso_provider_domains",
        ["domain"],
        unique=False,
    )
    op.create_index(
        "ix_sso_provider_domains_provider",
        "sso_provider_domains",
        ["provider_id"],
        unique=False,
    )
    op.create_table(
        "sso_identities",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_id", "subject", name="uq_sso_identities_provider_subject"),
        sa.UniqueConstraint("provider_id", "user_id", name="uq_sso_identities_provider_user"),
    )
    op.create_index("ix_sso_identities_user", "sso_identities", ["user_id"], unique=False)
    op.create_index(
        "ix_sso_identities_provider_subject",
        "sso_identities",
        ["provider_id", "subject"],
        unique=False,
    )
    op.create_table(
        "sso_auth_states",
        sa.Column("state", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("nonce", sa.String(length=255), nullable=False),
        sa.Column("pkce_verifier", sa.String(length=255), nullable=False),
        sa.Column("return_to", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sso_auth_states_expires", "sso_auth_states", ["expires_at"], unique=False)
    op.create_index("ix_sso_auth_states_provider", "sso_auth_states", ["provider_id"], unique=False)


def _create_document_indexes() -> None:
    op.create_index(
        "ix_documents_workspace_created",
        "documents",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_documents_workspace_last_run_id",
        "documents",
        ["workspace_id", "last_run_id"],
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
    op.create_index(
        "ix_documents_workspace_assignee",
        "documents",
        ["workspace_id", "assignee_user_id"],
        unique=False,
    )


def _upgrade_mssql() -> None:
    _ensure_mssql_alembic_version_length()
    _drop_mssql_document_event_triggers()
    _drop_mssql_run_env_triggers()
    _drop_document_event_legacy_columns_mssql()

    _drop_mssql_indexes()
    _drop_mssql_document_status_constraint()
    _drop_mssql_default_constraint(table="documents", column="status")
    _drop_mssql_default_constraint(table="documents", column="last_run_at")
    if not _column_exists("documents", "last_run_id"):
        op.add_column("documents", sa.Column("last_run_id", GUID(), nullable=True))
    if not _column_exists("documents", "comment_count"):
        op.add_column(
            "documents",
            sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if _column_exists("documents", "status"):
        op.drop_column("documents", "status")
    if _column_exists("documents", "last_run_at"):
        op.drop_column("documents", "last_run_at")

    _backfill_last_run_id_mssql()
    op.create_index(
        "ix_documents_workspace_last_run_id",
        "documents",
        ["workspace_id", "last_run_id"],
    )

    _create_document_comments_tables()
    _backfill_comment_count()
    _create_sso_tables()

    _create_mssql_document_event_triggers()
    _create_run_env_triggers_mssql()


def upgrade() -> None:
    _upgrade_mssql()


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for the collapsed migration.")
