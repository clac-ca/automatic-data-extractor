"""Historical placeholder after baseline rewrite.

This revision is intentionally a no-op. The current ``0001_initial_schema``
baseline already includes the ``runs.status = 'cancelled'`` constraint state.
"""

from __future__ import annotations

from typing import Optional

# Revision identifiers, used by Alembic.
revision = "0002_run_status_cancelled"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
