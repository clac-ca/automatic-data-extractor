"""Add document_events triggers for documents changes."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_document_event_triggers"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _dialect_name() -> Optional[str]:
    try:
        bind = op.get_bind()
    except Exception:
        return None
    return bind.dialect.name if bind is not None else None


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


def upgrade() -> None:
    dialect = _dialect_name()
    if dialect == "sqlite":
        _create_sqlite_triggers()
    elif dialect == "mssql":
        _create_mssql_triggers()
    else:  # pragma: no cover - guard for unexpected dialects
        raise RuntimeError(f"Unsupported dialect for document_events triggers: {dialect}")


def downgrade() -> None:
    dialect = _dialect_name()
    if dialect == "sqlite":
        _drop_sqlite_triggers()
    elif dialect == "mssql":
        _drop_mssql_triggers()
    else:  # pragma: no cover - guard for unexpected dialects
        raise RuntimeError(f"Unsupported dialect for document_events triggers: {dialect}")
