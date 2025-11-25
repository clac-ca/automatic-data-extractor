"""Extend runs with jobs metadata fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_runs_extended_metadata"
previous = "0006_jobs_config_fk"
down_revision = previous
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("retry_of_run_id", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("trace_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("submitted_by_user_id", sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column("config_version_id", sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column("input_documents", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("artifact_uri", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("output_uri", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("logs_uri", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))

        batch_op.create_foreign_key(
            "runs_submitted_by_user_id_fkey",
            "users",
            ["submitted_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index("runs_config_version_idx", "runs", ["config_version_id"], unique=False)
    op.create_index(
        "runs_workspace_created_idx",
        "runs",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index("runs_retry_of_idx", "runs", ["retry_of_run_id"], unique=False)


def downgrade() -> None:  # pragma: no cover - destructive downgrade
    op.drop_index("runs_retry_of_idx", table_name="runs")
    op.drop_index("runs_workspace_created_idx", table_name="runs")
    op.drop_index("runs_config_version_idx", table_name="runs")

    with op.batch_alter_table("runs", recreate="always") as batch_op:
        batch_op.drop_constraint("runs_submitted_by_user_id_fkey", type_="foreignkey")
        batch_op.drop_column("canceled_at")
        batch_op.drop_column("logs_uri")
        batch_op.drop_column("output_uri")
        batch_op.drop_column("artifact_uri")
        batch_op.drop_column("input_documents")
        batch_op.drop_column("config_version_id")
        batch_op.drop_column("submitted_by_user_id")
        batch_op.drop_column("trace_id")
        batch_op.drop_column("retry_of_run_id")
        batch_op.drop_column("attempt")
