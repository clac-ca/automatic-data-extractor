"""Make file name uniqueness apply only to active rows.

Revision ID: 0002_active_name_key_unique
Revises: 0001_initial_schema
Create Date: 2026-02-09
"""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_active_name_key_unique"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # Prior schema used a table-level UNIQUE constraint. Drop it if present.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'files_workspace_kind_name_key'
            ) THEN
                ALTER TABLE files
                    DROP CONSTRAINT files_workspace_kind_name_key;
            END IF;
        END
        $$;
        """
    )

    # Ensure we recreate the index as a partial unique index over active rows only.
    op.execute("DROP INDEX IF EXISTS files_workspace_kind_name_key;")
    op.execute(
        """
        CREATE UNIQUE INDEX files_workspace_kind_name_key
            ON files (workspace_id, kind, name_key)
            WHERE deleted_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS files_workspace_kind_name_key;")
    op.execute(
        """
        ALTER TABLE files
            ADD CONSTRAINT files_workspace_kind_name_key
            UNIQUE (workspace_id, kind, name_key);
        """
    )
