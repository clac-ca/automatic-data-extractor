"""Add valid_cells to run_table_columns table.

Revision ID: 0005_run_column_valid_cells
Revises: 0004_document_comment_threads
Create Date: 2026-05-21 09:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0005_run_column_valid_cells"
down_revision = "0004_document_comment_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_table_columns",
        sa.Column("valid_cells", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
