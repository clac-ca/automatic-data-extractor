"""Add job queue metadata columns and indexes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_job_queue_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("retry_of_job_id", sa.String(length=26), nullable=True))
        batch.add_column(sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("input_documents", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.drop_constraint("jobs_idempotency_key", type_="unique")
        batch.create_index("jobs_status_queued_idx", ["status", "queued_at"], unique=False)
        batch.create_index("jobs_retry_of_idx", ["retry_of_job_id"], unique=False)
        batch.create_index(
            "jobs_input_unique_idx",
            ["workspace_id", "config_version_id", "input_hash"],
            unique=True,
            sqlite_where=sa.text("retry_of_job_id IS NULL"),
            postgresql_where=sa.text("retry_of_job_id IS NULL"),
        )
    op.execute(
        "UPDATE jobs SET input_documents = '[]' WHERE input_documents IS NULL"
    )
    op.execute(
        "UPDATE jobs SET last_heartbeat = completed_at WHERE completed_at IS NOT NULL"
    )
    op.execute(
        "UPDATE jobs SET last_heartbeat = started_at WHERE last_heartbeat IS NULL AND started_at IS NOT NULL"
    )
    op.execute(
        "UPDATE jobs SET last_heartbeat = queued_at WHERE last_heartbeat IS NULL"
    )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("input_documents", server_default=None)


def downgrade() -> None:  # pragma: no cover - irreversible migration
    raise NotImplementedError("Downgrade is not supported for job queue metadata migration.")
