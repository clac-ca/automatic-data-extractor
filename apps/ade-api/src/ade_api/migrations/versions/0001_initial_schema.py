"""Initial ADE schema (Postgres).

Notes:
- UUID primary keys use Postgres uuidv7() defaults.
- Enums use VARCHAR + CHECK constraints (native_enum=False).
- JSON payloads are stored as JSONB.
- Installs the run-queue NOTIFY trigger used by ade-worker.
"""

from __future__ import annotations

from typing import Optional

from alembic import op

from ade_api.db import Base

# Revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision: Optional[str] = None
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # Import models so Base.metadata is populated.
    import ade_api.models  # noqa: F401

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

                    rand_b_hex := lpad(to_hex(floor(random() * 4294967296)::int), 8, '0')
                               || lpad(to_hex(floor(random() * 4294967296)::int), 8, '0');
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


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
