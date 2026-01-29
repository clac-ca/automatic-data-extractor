"""Simplify document history schema (drop version/idempotency fields).

This migration aligns files/file_versions to the new document history model:
- Drop idempotency_keys
- Remove files.version, files.doc_no, files.expires_at
- Rename files.parent_file_id -> files.source_file_id
- Rename file_versions.blob_version_id -> storage_version_id (nullable)
- Normalize file kinds and name_key values
- Backfill content_type for generated outputs
- Update document change triggers to use input kind and versionless updates
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0006_document_history_simplify"
down_revision: Optional[str] = "0005_document_changes_simple"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.drop_table("idempotency_keys")

    op.drop_constraint("files_workspace_doc_no_key", "files", type_="unique")
    op.drop_constraint("ck_files_file_kind", "files", type_="check")

    op.alter_column(
        "files",
        "parent_file_id",
        new_column_name="source_file_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
    )

    op.drop_column("files", "doc_no")
    op.drop_column("files", "version")
    op.drop_column("files", "expires_at")

    op.execute("UPDATE files SET kind = 'input' WHERE kind = 'document'")
    op.execute("UPDATE files SET kind = 'log' WHERE kind = 'run_log'")

    op.alter_column(
        "files",
        "kind",
        existing_type=sa.String(length=50),
        server_default="input",
    )
    op.create_check_constraint(
        "ck_files_file_kind",
        "files",
        "kind IN ('input', 'output', 'log', 'export')",
    )

    op.alter_column(
        "file_versions",
        "blob_version_id",
        new_column_name="storage_version_id",
        existing_type=sa.String(length=128),
        nullable=True,
    )

    op.execute(
        "UPDATE file_versions SET storage_version_id = NULL "
        "WHERE storage_version_id = sha256"
    )

    op.execute(
        "UPDATE files "
        "SET name_key = 'output:' || source_file_id "
        "WHERE kind = 'output' AND source_file_id IS NOT NULL"
    )

    op.execute(
        """
        UPDATE file_versions AS fv
           SET content_type = CASE
               WHEN lower(fv.filename_at_upload) LIKE '%.xlsx'
                 THEN 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
               WHEN lower(fv.filename_at_upload) LIKE '%.xls'
                 THEN 'application/vnd.ms-excel'
               WHEN lower(fv.filename_at_upload) LIKE '%.csv'
                 THEN 'text/csv'
               WHEN lower(fv.filename_at_upload) LIKE '%.pdf'
                 THEN 'application/pdf'
               ELSE 'application/octet-stream'
             END
          FROM files AS f
         WHERE fv.file_id = f.id
           AND f.kind = 'output'
           AND fv.origin = 'generated'
           AND fv.content_type IS NULL
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


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
