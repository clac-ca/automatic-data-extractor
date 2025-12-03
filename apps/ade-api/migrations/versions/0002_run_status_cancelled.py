"""Use British spelling for run cancellation status."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_run_status_cancelled"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


old_run_status = sa.Enum(
    "queued",
    "waiting_for_build",
    "running",
    "succeeded",
    "failed",
    "canceled",
    name="run_status",
    native_enum=False,
    length=20,
    create_constraint=True,
)

new_run_status = sa.Enum(
    "queued",
    "waiting_for_build",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="run_status",
    native_enum=False,
    length=20,
    create_constraint=True,
)

expanded_run_status = sa.Enum(
    "queued",
    "waiting_for_build",
    "running",
    "succeeded",
    "failed",
    "canceled",
    "cancelled",
    name="run_status",
    native_enum=False,
    length=20,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=old_run_status,
            type_=expanded_run_status,
            existing_nullable=False,
            existing_server_default="queued",
        )

    op.execute(sa.text("UPDATE runs SET status = 'cancelled' WHERE status = 'canceled'"))
    op.execute(
        sa.text(
            "UPDATE runs "
            "SET summary = REPLACE(summary, '\"status\": \"canceled\"', '\"status\": \"cancelled\"') "
            "WHERE summary LIKE '%\"status\": \"canceled\"%'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE runs "
            "SET summary = REPLACE(summary, '\"failure_code\": \"canceled\"', '\"failure_code\": \"cancelled\"') "
            "WHERE summary LIKE '%\"failure_code\": \"canceled\"%'"
        )
    )

    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=expanded_run_status,
            type_=new_run_status,
            existing_nullable=False,
            existing_server_default="queued",
        )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrade is not supported for this revision.")
