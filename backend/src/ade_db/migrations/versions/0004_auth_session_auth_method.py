"""Add auth_method metadata to auth_sessions."""

from __future__ import annotations

from typing import Optional

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "0004_auth_session_auth_method"
down_revision: Optional[str] = "0003_authn_rework"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column(
            "auth_method",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.execute(
        """
        ALTER TABLE auth_sessions
        ADD CONSTRAINT ck_auth_sessions_auth_method
        CHECK (auth_method IN ('password', 'sso', 'unknown'))
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS ck_auth_sessions_auth_method"
    )
    op.drop_column("auth_sessions", "auth_method")

