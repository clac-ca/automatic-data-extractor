"""Allow cancelled run status."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_run_status_cancelled"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _drop_existing_run_status_check() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            _constraint_name text;
        BEGIN
            SELECT conname
              INTO _constraint_name
              FROM pg_constraint
             WHERE conrelid = 'runs'::regclass
               AND contype = 'c'
               AND pg_get_constraintdef(oid) ILIKE '%status%'
               AND pg_get_constraintdef(oid) ILIKE '%queued%'
               AND pg_get_constraintdef(oid) ILIKE '%running%'
               AND pg_get_constraintdef(oid) ILIKE '%succeeded%'
               AND pg_get_constraintdef(oid) ILIKE '%failed%'
             ORDER BY conname
             LIMIT 1;

            IF _constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE runs DROP CONSTRAINT %I', _constraint_name);
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _drop_existing_run_status_check()
    op.execute(
        """
        ALTER TABLE runs
        ADD CONSTRAINT ck_runs_run_status
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'));
        """
    )


def downgrade() -> None:
    _drop_existing_run_status_check()
    op.execute(
        """
        ALTER TABLE runs
        ADD CONSTRAINT ck_runs_run_status
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed'));
        """
    )
