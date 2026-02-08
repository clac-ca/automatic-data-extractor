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


def _has_auth_method_column() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns("auth_sessions")
    return any(column["name"] == "auth_method" for column in columns)


def _has_auth_method_check_constraint() -> bool:
    bind = op.get_bind()
    query = sa.text(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conname = :constraint_name
          AND conrelid = 'auth_sessions'::regclass
        """
    )
    return bind.execute(
        query,
        {"constraint_name": "ck_auth_sessions_auth_method"},
    ).scalar_one_or_none() is not None


def upgrade() -> None:
    if not _has_auth_method_column():
        op.add_column(
            "auth_sessions",
            sa.Column(
                "auth_method",
                sa.String(length=32),
                nullable=False,
                server_default="unknown",
            ),
        )

    if not _has_auth_method_check_constraint():
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
    if _has_auth_method_column():
        op.drop_column("auth_sessions", "auth_method")
