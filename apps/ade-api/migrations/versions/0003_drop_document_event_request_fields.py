"""Drop request metadata columns from document_events and update triggers."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0003_drop_document_event_request_fields"
down_revision: Optional[str] = "0002_document_event_triggers"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _dialect_name() -> Optional[str]:
    try:
        bind = op.get_bind()
    except Exception:
        return None
    return bind.dialect.name if bind is not None else None


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


def _create_sqlite_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_events_insert
        AFTER INSERT ON documents
        BEGIN
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            VALUES (
                NEW.workspace_id,
                NEW.id,
                'document.changed',
                NEW.version,
                NEW.updated_at
            );
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_events_update
        AFTER UPDATE ON documents
        WHEN NEW.version != OLD.version
        BEGIN
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                occurred_at
            )
            VALUES (
                NEW.workspace_id,
                NEW.id,
                CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                        THEN 'document.deleted'
                    ELSE 'document.changed'
                END,
                NEW.version,
                NEW.updated_at
            );
        END;
        """
    )


def _drop_sqlite_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_documents_events_insert;")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_events_update;")


def _drop_sqlite_temp_table() -> None:
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_document_events;")


def _create_sqlite_triggers_legacy() -> None:
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_events_insert
        AFTER INSERT ON documents
        BEGIN
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                request_id,
                client_request_id,
                payload,
                occurred_at
            )
            VALUES (
                NEW.workspace_id,
                NEW.id,
                'document.changed',
                NEW.version,
                NULL,
                NULL,
                NULL,
                NEW.updated_at
            );
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_events_update
        AFTER UPDATE ON documents
        WHEN NEW.version != OLD.version
        BEGIN
            INSERT INTO document_events (
                workspace_id,
                document_id,
                event_type,
                document_version,
                request_id,
                client_request_id,
                payload,
                occurred_at
            )
            VALUES (
                NEW.workspace_id,
                NEW.id,
                CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                        THEN 'document.deleted'
                    ELSE 'document.changed'
                END,
                NEW.version,
                NULL,
                NULL,
                NULL,
                NEW.updated_at
            );
        END;
        """
    )


def _create_mssql_triggers() -> None:
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


def _create_mssql_triggers_legacy() -> None:
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
                request_id,
                client_request_id,
                payload,
                occurred_at
            )
            SELECT
                i.workspace_id,
                i.id,
                ''document.changed'',
                i.version,
                NULL,
                NULL,
                NULL,
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
                request_id,
                client_request_id,
                payload,
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
                NULL,
                NULL,
                NULL,
                i.updated_at
            FROM inserted AS i
            INNER JOIN deleted AS d ON d.id = i.id
            WHERE i.version <> d.version;
        END;
        ');
        """
    )


def _drop_mssql_triggers() -> None:
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


def upgrade() -> None:
    dialect = _dialect_name()
    if dialect == "sqlite":
        _drop_sqlite_temp_table()
        _drop_sqlite_triggers()
        columns = [
            name
            for name in ("request_id", "client_request_id", "payload")
            if _column_exists("document_events", name)
        ]
        if columns:
            with op.batch_alter_table("document_events") as batch_op:
                for name in columns:
                    batch_op.drop_column(name)
        _create_sqlite_triggers()
        return

    if dialect == "mssql":
        _ensure_mssql_alembic_version_length()
        _drop_mssql_triggers()
        for name in ("request_id", "client_request_id", "payload"):
            if _column_exists("document_events", name):
                op.drop_column("document_events", name)
        _create_mssql_triggers()
        return

    raise RuntimeError(f"Unsupported dialect for document_events migration: {dialect}")


def downgrade() -> None:
    dialect = _dialect_name()
    if dialect == "sqlite":
        _drop_sqlite_temp_table()
        _drop_sqlite_triggers()
        with op.batch_alter_table("document_events") as batch_op:
            if not _column_exists("document_events", "request_id"):
                batch_op.add_column(sa.Column("request_id", sa.String(length=128), nullable=True))
            if not _column_exists("document_events", "client_request_id"):
                batch_op.add_column(
                    sa.Column("client_request_id", sa.String(length=128), nullable=True)
                )
            if not _column_exists("document_events", "payload"):
                batch_op.add_column(sa.Column("payload", sa.JSON(), nullable=True))
        _create_sqlite_triggers_legacy()
        return

    if dialect == "mssql":
        _drop_mssql_triggers()
        if not _column_exists("document_events", "request_id"):
            op.add_column("document_events", sa.Column("request_id", sa.String(length=128), nullable=True))
        if not _column_exists("document_events", "client_request_id"):
            op.add_column(
                "document_events", sa.Column("client_request_id", sa.String(length=128), nullable=True)
            )
        if not _column_exists("document_events", "payload"):
            op.add_column("document_events", sa.Column("payload", sa.JSON(), nullable=True))
        _create_mssql_triggers_legacy()
        return

    raise RuntimeError(f"Unsupported dialect for document_events migration: {dialect}")
