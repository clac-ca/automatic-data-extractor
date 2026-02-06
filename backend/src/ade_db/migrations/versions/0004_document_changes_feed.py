"""Document change feed table + triggers."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0004_document_changes_feed"
down_revision: Optional[str] = "0003_run_queue_notify"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_files_notify_insert ON files;
        DROP TRIGGER IF EXISTS trg_files_notify_update ON files;
        DROP TRIGGER IF EXISTS trg_runs_notify_insert ON runs;
        DROP TRIGGER IF EXISTS trg_runs_notify_update ON runs;

        DROP FUNCTION IF EXISTS trg_files_notify_insert();
        DROP FUNCTION IF EXISTS trg_files_notify_update();
        DROP FUNCTION IF EXISTS trg_runs_notify_insert();
        DROP FUNCTION IF EXISTS trg_runs_notify_update();
        DROP FUNCTION IF EXISTS fn_document_event_notify();
        DROP FUNCTION IF EXISTS fn_document_event_notify(uuid, uuid, text, integer, timestamptz);
        DROP SEQUENCE IF EXISTS document_events_cursor_seq;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_changes (
            changed_at timestamptz NOT NULL DEFAULT now(),
            seq bigint GENERATED ALWAYS AS IDENTITY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL,
            op text NOT NULL CHECK (op IN ('upsert', 'delete')),
            PRIMARY KEY (changed_at, seq)
        ) PARTITION BY RANGE (changed_at);

        CREATE INDEX IF NOT EXISTS ix_document_changes_workspace_changed_seq
            ON document_changes (workspace_id, changed_at, seq);
        CREATE INDEX IF NOT EXISTS ix_document_changes_document_changed_seq
            ON document_changes (document_id, changed_at, seq);
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_document_changes_partition(_day date)
        RETURNS void AS $$
        DECLARE
            _partition_name text := format('document_changes_%s', to_char(_day, 'YYYY_MM_DD'));
            _start_ts timestamptz := _day::timestamptz;
            _end_ts timestamptz := (_day + 1)::timestamptz;
        BEGIN
            IF to_regclass(_partition_name) IS NOT NULL THEN
                RETURN;
            END IF;
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF document_changes '
                'FOR VALUES FROM (%L) TO (%L)',
                _partition_name,
                _start_ts,
                _end_ts
            );
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_document_changes_partitions(_start date, _days integer)
        RETURNS void AS $$
        DECLARE
            _idx integer;
            _target date;
        BEGIN
            IF _days IS NULL OR _days <= 0 THEN
                RETURN;
            END IF;
            FOR _idx IN 0..(_days - 1) LOOP
                _target := _start + _idx;
                PERFORM ensure_document_changes_partition(_target);
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION drop_old_document_changes_partitions(_retention_days integer)
        RETURNS integer AS $$
        DECLARE
            _cutoff date := current_date - _retention_days;
            _part record;
            _part_date date;
            _part_key text;
            _dropped integer := 0;
        BEGIN
            IF _retention_days IS NULL OR _retention_days <= 0 THEN
                RETURN 0;
            END IF;
            FOR _part IN
                SELECT c.relname
                FROM pg_class c
                JOIN pg_inherits i ON i.inhrelid = c.oid
                JOIN pg_class p ON i.inhparent = p.oid
                WHERE p.relname = 'document_changes'
            LOOP
                _part_key := substring(_part.relname from 'document_changes_(\\d{4}_\\d{2}_\\d{2})');
                IF _part_key IS NULL THEN
                    CONTINUE;
                END IF;
                _part_date := to_date(_part_key, 'YYYY_MM_DD');
                IF _part_date < _cutoff THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I', _part.relname);
                    _dropped := _dropped + 1;
                END IF;
            END LOOP;
            RETURN _dropped;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_document_change_record(
            _workspace_id uuid,
            _document_id uuid,
            _op text,
            _changed_at timestamptz
        )
        RETURNS void AS $$
        DECLARE
            _ts timestamptz;
            _seq bigint;
        BEGIN
            IF _workspace_id IS NULL OR _document_id IS NULL OR _op IS NULL THEN
                RETURN;
            END IF;
            _ts := COALESCE(_changed_at, now());
            PERFORM ensure_document_changes_partition(date_trunc('day', _ts)::date);
            INSERT INTO document_changes (changed_at, workspace_id, document_id, op)
            VALUES (_ts, _workspace_id, _document_id, _op)
            RETURNING seq INTO _seq;
            PERFORM pg_notify(
                'ade_document_changes',
                json_build_object(
                    'workspaceId', _workspace_id,
                    'documentId', _document_id,
                    'op', _op,
                    'changedAt', _ts,
                    'seq', _seq
                )::text
            );
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_files_document_changes_insert()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.kind = 'document' THEN
                PERFORM fn_document_change_record(
                    NEW.workspace_id,
                    NEW.id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_files_document_changes_insert ON files;")
    op.execute(
        """
        CREATE TRIGGER trg_files_document_changes_insert
        AFTER INSERT ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_files_document_changes_update()
        RETURNS trigger AS $$
        DECLARE
            _op text;
        BEGIN
            IF NEW.kind = 'document' AND (
                NEW.version IS DISTINCT FROM OLD.version
                OR NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
            ) THEN
                _op := CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN 'delete'
                    ELSE 'upsert'
                END;
                PERFORM fn_document_change_record(
                    NEW.workspace_id,
                    NEW.id,
                    _op,
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_files_document_changes_update ON files;")
    op.execute(
        """
        CREATE TRIGGER trg_files_document_changes_update
        AFTER UPDATE ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_document_changes_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_file_tags_document_changes_insert()
        RETURNS trigger AS $$
        DECLARE
            _workspace_id uuid;
            _kind text;
        BEGIN
            SELECT workspace_id, kind
              INTO _workspace_id, _kind
              FROM files
             WHERE id = NEW.file_id;
            IF _workspace_id IS NOT NULL AND _kind = 'document' THEN
                PERFORM fn_document_change_record(
                    _workspace_id,
                    NEW.file_id,
                    'upsert',
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_file_tags_document_changes_insert ON file_tags;")
    op.execute(
        """
        CREATE TRIGGER trg_file_tags_document_changes_insert
        AFTER INSERT ON file_tags
        FOR EACH ROW
        EXECUTE FUNCTION trg_file_tags_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_file_tags_document_changes_delete()
        RETURNS trigger AS $$
        DECLARE
            _workspace_id uuid;
            _kind text;
        BEGIN
            SELECT workspace_id, kind
              INTO _workspace_id, _kind
              FROM files
             WHERE id = OLD.file_id;
            IF _workspace_id IS NOT NULL AND _kind = 'document' THEN
                PERFORM fn_document_change_record(
                    _workspace_id,
                    OLD.file_id,
                    'upsert',
                    now()
                );
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_file_tags_document_changes_delete ON file_tags;")
    op.execute(
        """
        CREATE TRIGGER trg_file_tags_document_changes_delete
        AFTER DELETE ON file_tags
        FOR EACH ROW
        EXECUTE FUNCTION trg_file_tags_document_changes_delete();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_document_changes_insert()
        RETURNS trigger AS $$
        DECLARE
            _document_id uuid;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL THEN
                SELECT f.id
                  INTO _document_id
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'document';

                IF _document_id IS NOT NULL THEN
                    PERFORM fn_document_change_record(
                        NEW.workspace_id,
                        _document_id,
                        'upsert',
                        clock_timestamp()
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_document_changes_insert ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_document_changes_insert
        AFTER INSERT ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_runs_document_changes_update()
        RETURNS trigger AS $$
        DECLARE
            _document_id uuid;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.started_at IS DISTINCT FROM OLD.started_at
                OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
                OR NEW.output_file_version_id IS DISTINCT FROM OLD.output_file_version_id
                OR NEW.error_message IS DISTINCT FROM OLD.error_message
            ) THEN
                SELECT f.id
                  INTO _document_id
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'document';

                IF _document_id IS NOT NULL THEN
                    PERFORM fn_document_change_record(
                        NEW.workspace_id,
                        _document_id,
                        'upsert',
                        clock_timestamp()
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_runs_document_changes_update ON runs;")
    op.execute(
        """
        CREATE TRIGGER trg_runs_document_changes_update
        AFTER UPDATE ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_document_changes_update();
        """
    )


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
