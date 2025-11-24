"""Introduce run tracking tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_runs_tables"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

RUNSTATUS = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "canceled",
    name="run_status",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    bind = op.get_bind()
    RUNSTATUS.create(bind, checkfirst=True)

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("status", RUNSTATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index("runs_config_idx", "runs", ["config_id"], unique=False)
    op.create_index("runs_workspace_idx", "runs", ["workspace_id"], unique=False)
    op.create_index("runs_status_idx", "runs", ["status"], unique=False)

    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("stream", sa.String(length=20), nullable=False, server_default="stdout"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("run_logs_run_id_idx", "run_logs", ["run_id"], unique=False)
    op.create_index("run_logs_stream_idx", "run_logs", ["stream"], unique=False)


def downgrade() -> None:  # pragma: no cover - destructive downgrade
    op.drop_index("run_logs_stream_idx", table_name="run_logs")
    op.drop_index("run_logs_run_id_idx", table_name="run_logs")
    op.drop_table("run_logs")

    op.drop_index("runs_status_idx", table_name="runs")
    op.drop_index("runs_workspace_idx", table_name="runs")
    op.drop_index("runs_config_idx", table_name="runs")
    op.drop_table("runs")

    bind = op.get_bind()
    RUNSTATUS.drop(bind, checkfirst=True)
