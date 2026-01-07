"""Drop document upload sessions table."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0005_remove_document_upload_sessions"
down_revision: Optional[str] = "0004_environments_runs_no_builds"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.drop_table("document_upload_sessions")


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
