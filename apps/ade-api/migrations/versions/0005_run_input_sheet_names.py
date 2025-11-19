"""Add input sheet names array to runs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_run_input_sheet_names"
previous = "0004_run_input_metadata"
down_revision = previous
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("input_sheet_names", sa.JSON(), nullable=True))


def downgrade() -> None:  # pragma: no cover - destructive downgrade
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.drop_column("input_sheet_names")
