"""Add run operation column and remove environments table."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0008_run_operation_and_drop_environments"
down_revision: Optional[str] = "0007_remove_engine_spec"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _has_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "runs" not in table_names:
        return

    run_columns = {column["name"] for column in inspector.get_columns("runs")}

    if "operation" not in run_columns:
        op.add_column(
            "runs",
            sa.Column(
                "operation",
                sa.String(length=20),
                nullable=False,
                server_default="process",
            ),
        )
        run_columns.add("operation")

    if not _has_constraint(inspector, "runs", "ck_runs_operation"):
        op.create_check_constraint(
            "ck_runs_operation",
            "runs",
            "operation IN ('validate','process')",
        )

    op.execute("UPDATE runs SET operation = 'process' WHERE operation IS NULL")

    run_col_defs = {column["name"]: column for column in inspector.get_columns("runs")}
    input_col = run_col_defs.get("input_file_version_id")
    if input_col is not None and bool(input_col.get("nullable")) is False:
        op.alter_column("runs", "input_file_version_id", nullable=True)

    inspector = sa.inspect(bind)
    if _has_index(inspector, "runs", "uq_runs_active_job"):
        op.drop_index("uq_runs_active_job", table_name="runs")

    op.create_index(
        "uq_runs_active_job",
        "runs",
        ["workspace_id", "input_file_version_id", "configuration_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running') AND operation = 'process'"),
    )

    if not _has_index(inspector, "runs", "ix_runs_operation"):
        op.create_index("ix_runs_operation", "runs", ["operation"], unique=False)

    inspector = sa.inspect(bind)
    if "environments" in inspector.get_table_names():
        op.drop_table("environments")


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
