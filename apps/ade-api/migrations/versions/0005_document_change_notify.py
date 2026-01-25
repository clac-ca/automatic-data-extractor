"""Document change NOTIFY triggers (best-effort)."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0005_document_change_notify"
down_revision: Optional[str] = "0004_run_queue_notify_clock_ts"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_documents_events_insert ON documents;
        DROP TRIGGER IF EXISTS trg_documents_events_update ON documents;
        DROP TRIGGER IF EXISTS trg_runs_events_insert ON runs;
        DROP TRIGGER IF EXISTS trg_runs_events_update ON runs;
        DROP TRIGGER IF EXISTS trg_environments_events_update ON environments;

        DROP FUNCTION IF EXISTS trg_documents_events_insert();
        DROP FUNCTION IF EXISTS trg_documents_events_update();
        DROP FUNCTION IF EXISTS trg_runs_events_insert();
        DROP FUNCTION IF EXISTS trg_runs_events_update();
        DROP FUNCTION IF EXISTS trg_environments_events_update();
        """
    )

    op.execute("DROP TABLE IF EXISTS document_events;")

    op.execute("CREATE SEQUENCE IF NOT EXISTS document_events_cursor_seq;")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_document_change_notify(
            _workspace_id uuid,
            _document_id uuid,
            _event_type text,
            _document_version integer,
            _occurred_at timestamptz
        )
        RETURNS void AS $$
        DECLARE
            _cursor bigint;
        BEGIN
            _cursor := nextval('document_events_cursor_seq');
            PERFORM pg_notify(
                'ade_document_changed',
                json_build_object(
                    'cursor', _cursor,
                    'workspaceId', _workspace_id,
                    'documentId', _document_id,
                    'type', _event_type,
                    'documentVersion', _document_version,
                    'occurredAt', _occurred_at
                )::text
            );
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_documents_notify_insert()
        RETURNS trigger AS $$
        BEGIN
            PERFORM fn_document_change_notify(
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
    op.execute("DROP TRIGGER IF EXISTS trg_documents_notify_insert ON documents;")
    op.execute(
        """
        CREATE TRIGGER trg_documents_notify_insert
        AFTER INSERT ON documents
        FOR EACH ROW
        EXECUTE FUNCTION trg_documents_notify_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_documents_notify_update()
        RETURNS trigger AS $$
        DECLARE
            _event_type text;
        BEGIN
            IF NEW.version IS DISTINCT FROM OLD.version THEN
                _event_type := CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                        THEN 'document.deleted'
                    ELSE 'document.changed'
                END;
                PERFORM fn_document_change_notify(
                    NEW.workspace_id,
                    NEW.id,
                    _event_type,
                    NEW.version,
                    NEW.updated_at
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_documents_notify_update ON documents;")
    op.execute(
        """
        CREATE TRIGGER trg_documents_notify_update
        AFTER UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION trg_documents_notify_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_notify_insert()
        RETURNS trigger AS $$
        DECLARE
            _version integer;
        BEGIN
            IF NEW.input_document_id IS NOT NULL THEN
                SELECT d.version INTO _version
                FROM documents AS d
                WHERE d.id = NEW.input_document_id;
                IF _version IS NOT NULL THEN
                    PERFORM fn_document_change_notify(
                        NEW.workspace_id,
                        NEW.input_document_id,
                        'document.changed',
                        _version,
                        COALESCE(NEW.created_at, now())
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_notify_insert ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_notify_insert
        AFTER INSERT ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_notify_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_notify_update()
        RETURNS trigger AS $$
        DECLARE
            _version integer;
        BEGIN
            IF NEW.input_document_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.started_at IS DISTINCT FROM OLD.started_at
                OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
                OR NEW.output_path IS DISTINCT FROM OLD.output_path
                OR NEW.error_message IS DISTINCT FROM OLD.error_message
            ) THEN
                SELECT d.version INTO _version
                FROM documents AS d
                WHERE d.id = NEW.input_document_id;
                IF _version IS NOT NULL THEN
                    PERFORM fn_document_change_notify(
                        NEW.workspace_id,
                        NEW.input_document_id,
                        'document.changed',
                        _version,
                        now()
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_notify_update ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_notify_update
        AFTER UPDATE ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_notify_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_environments_notify_update()
        RETURNS trigger AS $$
        DECLARE
            rec RECORD;
        BEGIN
            IF (OLD.status = 'ready' AND NEW.status <> 'ready')
                OR (OLD.status <> 'ready' AND NEW.status = 'ready') THEN
                FOR rec IN
                    SELECT
                        doc.workspace_id AS workspace_id,
                        doc.id AS document_id,
                        doc.version AS document_version
                    FROM runs AS r
                    INNER JOIN documents AS doc ON doc.last_run_id = r.id
                    WHERE r.workspace_id = NEW.workspace_id
                      AND r.configuration_id = NEW.configuration_id
                      AND r.engine_spec = NEW.engine_spec
                      AND r.deps_digest = NEW.deps_digest
                      AND r.status = 'queued'
                LOOP
                    PERFORM fn_document_change_notify(
                        rec.workspace_id,
                        rec.document_id,
                        'document.changed',
                        rec.document_version,
                        now()
                    );
                END LOOP;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_environments_notify_update ON environments;")
    op.execute(
        """
        CREATE TRIGGER trg_environments_notify_update
        AFTER UPDATE ON environments
        FOR EACH ROW
        EXECUTE FUNCTION trg_environments_notify_update();
        """
    )


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
