"""Historical placeholder after auth baseline rewrite.

This revision is intentionally a no-op. The authn/session/reset/MFA schema is
now part of the ``0001_initial_schema`` baseline.
"""

from __future__ import annotations

from typing import Optional

# Revision identifiers, used by Alembic.
revision = "0003_authn_rework"
down_revision: Optional[str] = "0002_run_status_cancelled"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
