"""Notify run queue whenever status becomes queued (ignore available_at)."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0006_run_queue_notify"
down_revision: Optional[str] = "0005_document_change_notify"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
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
        """
    )


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
