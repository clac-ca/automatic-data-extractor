"""Legacy migration retained for continuity; no-op after consolidating sheet fields."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0003_multi_sheet_runs"
down_revision: Optional[str] = "0002_single_file_runs"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # No-op: input_sheet_names is already present from initial schema.
    pass


def downgrade() -> None:  # pragma: no cover
    pass
