"""Add durable run queue fields and indexes.

Revision ID: 0002_run_queue_refactor
Revises: 0001_initial_schema
Create Date: 2025-02-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from ade_api.db import UUIDType

# revision identifiers, used by Alembic.
revision = "0002_run_queue_refactor"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.alter_column(
            "build_id",
            existing_type=UUIDType(),
            nullable=True,
        )
        batch.add_column(
            sa.Column(
                "available_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(
            sa.Column(
                "run_options",
                sa.JSON(),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default="3",
            )
        )
        batch.add_column(
            sa.Column(
                "claimed_by",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "claim_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.create_index(
        "ix_runs_claim",
        "runs",
        ["status", "available_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_runs_active_job",
        "runs",
        ["workspace_id", "input_document_id", "configuration_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued','running')"),
        mssql_where=sa.text("status IN ('queued','running')"),
        postgresql_where=sa.text("status IN ('queued','running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_runs_active_job", table_name="runs")
    op.drop_index("ix_runs_claim", table_name="runs")

    with op.batch_alter_table("runs") as batch:
        batch.drop_column("claim_expires_at")
        batch.drop_column("claimed_by")
        batch.drop_column("max_attempts")
        batch.drop_column("attempt_count")
        batch.drop_column("run_options")
        batch.drop_column("available_at")
        batch.alter_column(
            "build_id",
            existing_type=UUIDType(),
            nullable=False,
        )
