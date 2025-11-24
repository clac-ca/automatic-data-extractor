"""Capture run input metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_run_input_metadata"
down_revision = "0003_builds_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("input_document_id", sa.String(length=26), nullable=True)
        )
        batch_op.add_column(sa.Column("input_sheet_name", sa.String(length=64), nullable=True))
        batch_op.create_index(
            "runs_input_document_idx",
            ["input_document_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "runs_input_document_id_fkey",
            "documents",
            ["input_document_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:  # pragma: no cover - destructive downgrade
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.drop_constraint("runs_input_document_id_fkey", type_="foreignkey")
        batch_op.drop_index("runs_input_document_idx")
        batch_op.drop_column("input_sheet_name")
        batch_op.drop_column("input_document_id")
