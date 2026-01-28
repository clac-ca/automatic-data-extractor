"""Document event NOTIFY triggers (best-effort, no event table).

Notes:
- Creates a cursor sequence used for SSE Last-Event-ID.
- Installs NOTIFY triggers for files + runs.
"""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_document_event_notify"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS document_events_cursor_seq;

        CREATE OR REPLACE FUNCTION fn_document_event_notify(
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
                'ade_document_events',
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
        CREATE OR REPLACE FUNCTION trg_files_notify_insert()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.kind = 'document' THEN
                PERFORM fn_document_event_notify(
                    NEW.workspace_id,
                    NEW.id,
                    'document.changed',
                    NEW.version,
                    COALESCE(NEW.updated_at, now())
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_files_notify_insert ON files;")
    op.execute(
        """
        CREATE TRIGGER trg_files_notify_insert
        AFTER INSERT ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_notify_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_files_notify_update()
        RETURNS trigger AS $$
        DECLARE
            _event_type text;
        BEGIN
            IF NEW.kind = 'document' AND NEW.version IS DISTINCT FROM OLD.version THEN
                _event_type := CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                        THEN 'document.deleted'
                    ELSE 'document.changed'
                END;
                PERFORM fn_document_event_notify(
                    NEW.workspace_id,
                    NEW.id,
                    _event_type,
                    NEW.version,
                    COALESCE(NEW.updated_at, now())
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_files_notify_update ON files;")
    op.execute(
        """
        CREATE TRIGGER trg_files_notify_update
        AFTER UPDATE ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_notify_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_notify_insert()
        RETURNS trigger AS $$
        DECLARE
            _document_id uuid;
            _document_version integer;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL THEN
                SELECT f.id, f.version
                  INTO _document_id, _document_version
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'document';

                IF _document_id IS NOT NULL THEN
                    PERFORM fn_document_event_notify(
                        NEW.workspace_id,
                        _document_id,
                        'document.changed',
                        _document_version,
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
            _document_id uuid;
            _document_version integer;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.started_at IS DISTINCT FROM OLD.started_at
                OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
                OR NEW.output_file_version_id IS DISTINCT FROM OLD.output_file_version_id
                OR NEW.error_message IS DISTINCT FROM OLD.error_message
            ) THEN
                SELECT f.id, f.version
                  INTO _document_id, _document_version
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'document';

                IF _document_id IS NOT NULL THEN
                    PERFORM fn_document_event_notify(
                        NEW.workspace_id,
                        _document_id,
                        'document.changed',
                        _document_version,
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


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
