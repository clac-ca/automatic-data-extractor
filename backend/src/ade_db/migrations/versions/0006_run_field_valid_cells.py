"""Add valid_cells to run_fields table.

Revision ID: 0006_run_field_valid_cells
Revises: 0005_run_column_valid_cells
Create Date: 2026-05-21 10:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0006_run_field_valid_cells"
down_revision = "0005_run_column_valid_cells"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_fields",
        sa.Column("valid_cells", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
