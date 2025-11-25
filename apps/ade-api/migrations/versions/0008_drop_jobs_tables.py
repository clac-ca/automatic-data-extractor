"""Drop legacy jobs tables and enums now superseded by runs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_drop_jobs_tables"
down_revision = "0007_runs_extended_metadata"
branch_labels = None
depends_on = None

JOBSTATUS = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="jobstatus",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    op.drop_index("jobs_input_unique_idx", table_name="jobs")
    op.drop_index("jobs_retry_of_idx", table_name="jobs")
    op.drop_index("jobs_status_queued_idx", table_name="jobs")
    op.drop_index("jobs_input_idx", table_name="jobs")
    op.drop_index("jobs_config_version_idx", table_name="jobs")
    op.drop_index("jobs_workspace_idx", table_name="jobs")
    op.drop_table("jobs")
    bind = op.get_bind()
    JOBSTATUS.drop(bind, checkfirst=True)


def downgrade() -> None:  # pragma: no cover - one-way migration
    raise NotImplementedError("Dropping jobs is irreversible without backup")
