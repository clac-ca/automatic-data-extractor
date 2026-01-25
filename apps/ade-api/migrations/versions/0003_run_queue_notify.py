"""Run queue NOTIFY trigger for event-driven workers."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0003_run_queue_notify"
down_revision: Optional[str] = "0002_collapsed_current_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_runs_notify_queued ON runs;
        DROP FUNCTION IF EXISTS trg_runs_notify_queued();
        CREATE OR REPLACE FUNCTION fn_runs_notify_queued()
        RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'INSERT' AND NEW.status = 'queued' AND NEW.available_at <= now())
               OR (TG_OP = 'UPDATE'
                   AND NEW.status = 'queued'
                   AND NEW.status IS DISTINCT FROM OLD.status
                   AND NEW.available_at <= now()) THEN
                PERFORM pg_notify('ade_run_queued', NEW.id::text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_runs_notify_queued
        AFTER INSERT OR UPDATE OF status ON runs
        FOR EACH ROW
        EXECUTE FUNCTION fn_runs_notify_queued();
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_runs_status_created_at ON runs (status, created_at);"
    )


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
