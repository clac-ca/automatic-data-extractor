"""Initial ADE schema (Postgres), squashed to current head.

Notes:
- UUID primary keys use Postgres uuidv7() defaults.
- Enums use VARCHAR + CHECK constraints (native_enum=False).
- JSON payloads are stored as JSONB.
- Includes publish-era schema primitives (``RunOperation.PUBLISH``,
  ``configurations.published_digest``, and active publish run index).
- Installs run queue and document change feed triggers.
"""

from __future__ import annotations

from typing import Optional

from alembic import op

from ade_db.metadata import Base

# Revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision: Optional[str] = None
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # Import models so Base.metadata is populated.
    import ade_db.models  # noqa: F401

    bind = op.get_bind()
    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'uuidv7'
                  AND pg_function_is_visible(oid)
            ) THEN
                CREATE FUNCTION uuidv7() RETURNS uuid AS $func$
                DECLARE
                    ts_ms bigint;
                    ts_hex text;
                    rand_a int;
                    rand_a_hex text;
                    rand_b_hex text;
                    variant_nibble int;
                    uuid_hex text;
                BEGIN
                    ts_ms := floor(extract(epoch from clock_timestamp()) * 1000)::bigint;
                    ts_hex := lpad(to_hex(ts_ms), 12, '0');

                    rand_a := floor(random() * 4096)::int;
                    rand_a_hex := lpad(to_hex(rand_a), 3, '0');

                    rand_b_hex := lpad(to_hex(floor(random() * 4294967296)::bigint), 8, '0')
                               || lpad(to_hex(floor(random() * 4294967296)::bigint), 8, '0');
                    variant_nibble := (floor(random() * 4)::int) + 8;
                    rand_b_hex := to_hex(variant_nibble) || substring(rand_b_hex from 2);

                    uuid_hex := ts_hex || '7' || rand_a_hex || rand_b_hex;
                    RETURN (
                        substring(uuid_hex from 1 for 8) || '-' ||
                        substring(uuid_hex from 9 for 4) || '-' ||
                        substring(uuid_hex from 13 for 4) || '-' ||
                        substring(uuid_hex from 17 for 4) || '-' ||
                        substring(uuid_hex from 21 for 12)
                    )::uuid;
                END;
                $func$ LANGUAGE plpgsql;
            END IF;
        END
        $do$;
        """
    )
    Base.metadata.create_all(bind=bind)

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_runs_notify_queued ON runs;
        DROP FUNCTION IF EXISTS fn_runs_notify_queued();
        CREATE OR REPLACE FUNCTION fn_runs_notify_queued()
        RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'INSERT' AND NEW.status = 'queued')
               OR (TG_OP = 'UPDATE'
                   AND NEW.status = 'queued'
                   AND NEW.status IS DISTINCT FROM OLD.status) THEN
                PERFORM pg_notify('ade_run_queued', NEW.id::text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_runs_notify_queued
        AFTER INSERT OR UPDATE OF status ON runs
        FOR EACH ROW
        EXECUTE FUNCTION fn_runs_notify_queued();
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_changes (
            id bigserial PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL,
            op text NOT NULL CHECK (op IN ('upsert', 'delete')),
            changed_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_document_changes_workspace_id_id
            ON document_changes (workspace_id, id);
        CREATE INDEX IF NOT EXISTS ix_document_changes_document_id_id
            ON document_changes (document_id, id);
        CREATE INDEX IF NOT EXISTS ix_document_changes_changed_at
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
            IF NEW.kind = 'input' THEN
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
        CREATE OR REPLACE FUNCTION trg_files_document_changes_update()
        RETURNS trigger AS $$
        DECLARE
            _op text;
        BEGIN
            IF NEW.kind = 'input' AND (
                NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
                OR NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.name_key IS DISTINCT FROM OLD.name_key
                OR NEW.attributes IS DISTINCT FROM OLD.attributes
                OR NEW.assignee_user_id IS DISTINCT FROM OLD.assignee_user_id
                OR NEW.comment_count IS DISTINCT FROM OLD.comment_count
                OR NEW.last_run_id IS DISTINCT FROM OLD.last_run_id
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
            IF _workspace_id IS NOT NULL AND _kind = 'input' THEN
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
            IF _workspace_id IS NOT NULL AND _kind = 'input' THEN
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
                   AND f.kind = 'input';

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
                   AND f.kind = 'input';

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

    op.execute("DROP TRIGGER IF EXISTS trg_files_document_changes_insert ON files;")
    op.execute("DROP TRIGGER IF EXISTS trg_files_document_changes_update ON files;")
    op.execute("DROP TRIGGER IF EXISTS trg_file_tags_document_changes_insert ON file_tags;")
    op.execute("DROP TRIGGER IF EXISTS trg_file_tags_document_changes_delete ON file_tags;")
    op.execute("DROP TRIGGER IF EXISTS trg_runs_document_changes_insert ON runs;")
    op.execute("DROP TRIGGER IF EXISTS trg_runs_document_changes_update ON runs;")

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
        CREATE TRIGGER trg_files_document_changes_update
        AFTER UPDATE ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_document_changes_update();
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
        CREATE TRIGGER trg_file_tags_document_changes_delete
        AFTER DELETE ON file_tags
        FOR EACH ROW
        EXECUTE FUNCTION trg_file_tags_document_changes_delete();
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
        CREATE TRIGGER trg_runs_document_changes_update
        AFTER UPDATE ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_document_changes_update();
        """
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
