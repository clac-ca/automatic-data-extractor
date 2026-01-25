"""Postgres triggers for document/run/environment events."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_collapsed_current_schema"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _create_document_event_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_documents_events_insert()
        RETURNS trigger AS $$
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
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_documents_events_insert ON documents;")
    op.execute(
        """
        CREATE TRIGGER trg_documents_events_insert
        AFTER INSERT ON documents
        FOR EACH ROW
        EXECUTE FUNCTION trg_documents_events_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_documents_events_update()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.version IS DISTINCT FROM OLD.version THEN
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
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_documents_events_update ON documents;")
    op.execute(
        """
        CREATE TRIGGER trg_documents_events_update
        AFTER UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION trg_documents_events_update();
        """
    )


def _create_run_env_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_events_insert()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.input_document_id IS NOT NULL THEN
                INSERT INTO document_events (
                    workspace_id,
                    document_id,
                    event_type,
                    document_version,
                    occurred_at
                )
                SELECT
                    NEW.workspace_id,
                    NEW.input_document_id,
                    'document.changed',
                    d.version,
                    COALESCE(NEW.created_at, now())
                FROM documents AS d
                WHERE d.id = NEW.input_document_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_events_insert ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_events_insert
        AFTER INSERT ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_events_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_events_update()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.input_document_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.started_at IS DISTINCT FROM OLD.started_at
                OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
                OR NEW.output_path IS DISTINCT FROM OLD.output_path
                OR NEW.error_message IS DISTINCT FROM OLD.error_message
            ) THEN
                INSERT INTO document_events (
                    workspace_id,
                    document_id,
                    event_type,
                    document_version,
                    occurred_at
                )
                SELECT
                    NEW.workspace_id,
                    NEW.input_document_id,
                    'document.changed',
                    d.version,
                    now()
                FROM documents AS d
                WHERE d.id = NEW.input_document_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_events_update ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_events_update
        AFTER UPDATE ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_events_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_environments_events_update()
        RETURNS trigger AS $$
        BEGIN
            IF (OLD.status = 'ready' AND NEW.status <> 'ready')
                OR (OLD.status <> 'ready' AND NEW.status = 'ready') THEN
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
                    'document.changed',
                    doc.version,
                    now()
                FROM runs AS r
                INNER JOIN documents AS doc ON doc.last_run_id = r.id
                WHERE r.workspace_id = NEW.workspace_id
                  AND r.configuration_id = NEW.configuration_id
                  AND r.engine_spec = NEW.engine_spec
                  AND r.deps_digest = NEW.deps_digest
                  AND r.status = 'queued';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_environments_events_update ON environments;")
    op.execute(
        """
        CREATE TRIGGER trg_environments_events_update
        AFTER UPDATE ON environments
        FOR EACH ROW
        EXECUTE FUNCTION trg_environments_events_update();
        """
    )


def upgrade() -> None:
    _create_document_event_triggers()
    _create_run_env_triggers()


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for the collapsed migration.")
