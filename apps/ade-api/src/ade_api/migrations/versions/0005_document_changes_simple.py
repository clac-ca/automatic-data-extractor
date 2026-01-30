"""Simplify document change feed to numeric cursor + shared trigger function."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0005_document_changes_simple"
down_revision: Optional[str] = "0004_document_changes_feed"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_files_document_changes_insert ON files;
        DROP TRIGGER IF EXISTS trg_files_document_changes_update ON files;
        DROP TRIGGER IF EXISTS trg_file_tags_document_changes_insert ON file_tags;
        DROP TRIGGER IF EXISTS trg_file_tags_document_changes_delete ON file_tags;
        DROP TRIGGER IF EXISTS trg_runs_document_changes_insert ON runs;
        DROP TRIGGER IF EXISTS trg_runs_document_changes_update ON runs;

        DROP FUNCTION IF EXISTS trg_files_document_changes_insert();
        DROP FUNCTION IF EXISTS trg_files_document_changes_update();
        DROP FUNCTION IF EXISTS trg_file_tags_document_changes_insert();
        DROP FUNCTION IF EXISTS trg_file_tags_document_changes_delete();
        DROP FUNCTION IF EXISTS trg_runs_document_changes_insert();
        DROP FUNCTION IF EXISTS trg_runs_document_changes_update();
        DROP FUNCTION IF EXISTS fn_document_change_record(uuid, uuid, text, timestamptz);
        DROP FUNCTION IF EXISTS fn_document_change_record(uuid, uuid, text);
        DROP FUNCTION IF EXISTS ensure_document_changes_partition(date);
        DROP FUNCTION IF EXISTS ensure_document_changes_partitions(date, integer);
        DROP FUNCTION IF EXISTS drop_old_document_changes_partitions(integer);

        DROP TABLE IF EXISTS document_changes CASCADE;
        """
    )

    op.execute(
        """
        CREATE TABLE document_changes (
            id bigserial PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL,
            op text NOT NULL CHECK (op IN ('upsert', 'delete')),
            changed_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_document_changes_workspace_id_id
            ON document_changes (workspace_id, id);
        CREATE INDEX ix_document_changes_document_id_id
            ON document_changes (document_id, id);
        CREATE INDEX ix_document_changes_changed_at
            ON document_changes (changed_at);
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION record_document_change(
            _workspace_id uuid,
            _document_id uuid,
            _op text,
            _changed_at timestamptz
        )
        RETURNS bigint AS $$
        DECLARE
            _ts timestamptz;
            _id bigint;
        BEGIN
            IF _workspace_id IS NULL OR _document_id IS NULL OR _op IS NULL THEN
                RETURN NULL;
            END IF;
            _ts := COALESCE(_changed_at, clock_timestamp());
            INSERT INTO document_changes (workspace_id, document_id, op, changed_at)
            VALUES (_workspace_id, _document_id, _op, _ts)
            RETURNING id INTO _id;
            PERFORM pg_notify(
                'ade_document_changes',
                json_build_object(
                    'workspaceId', _workspace_id,
                    'documentId', _document_id,
                    'op', _op,
                    'id', _id
                )::text
            );
            RETURN _id;
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
                PERFORM record_document_change(
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
                PERFORM record_document_change(
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
                PERFORM record_document_change(
                    _workspace_id,
                    NEW.file_id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
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
                PERFORM record_document_change(
                    _workspace_id,
                    OLD.file_id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
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
                    PERFORM record_document_change(
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
                    PERFORM record_document_change(
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
