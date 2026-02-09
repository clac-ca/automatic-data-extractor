"""Add singleton application_settings table for runtime settings."""

from __future__ import annotations

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_application_settings"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS application_settings (
            id smallint PRIMARY KEY,
            schema_version integer NOT NULL DEFAULT 2,
            data jsonb NOT NULL DEFAULT '{}'::jsonb,
            revision bigint NOT NULL DEFAULT 1,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid NULL,
            CONSTRAINT ck_application_settings_singleton CHECK (id = 1),
            CONSTRAINT ck_application_settings_data_object CHECK (jsonb_typeof(data) = 'object')
        );
        """
    )

    op.execute(
        """
        INSERT INTO application_settings (
            id,
            schema_version,
            data,
            revision,
            updated_at,
            updated_by
        )
        VALUES (1, 2, '{}'::jsonb, 1, now(), NULL)
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS application_settings;")
