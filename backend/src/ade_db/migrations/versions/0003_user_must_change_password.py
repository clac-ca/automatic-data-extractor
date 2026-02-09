"""Add users.must_change_password flag for forced password rotation."""

from __future__ import annotations

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0003_user_must_change_password"
down_revision: str | None = "0002_application_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS must_change_password;
        """
    )
