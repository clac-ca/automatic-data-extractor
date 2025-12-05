"""Align runs table with single-file contract by dropping plural input fields."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_single_file_runs"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("input_documents")
        batch.drop_column("input_sheet_names")


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrade is not supported for this revision.")
