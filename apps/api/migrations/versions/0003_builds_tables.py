"""Create API-facing build tracking tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_builds_tables"
down_revision = "0002_runs_tables"
branch_labels = None
depends_on = None

BUILDSTATUS = sa.Enum(
    "queued",
    "building",
    "active",
    "failed",
    "canceled",
    name="api_build_status",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    bind = op.get_bind()
    BUILDSTATUS.create(bind, checkfirst=True)

    op.create_table(
        "builds",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_build_id", sa.String(length=26), nullable=True),
        sa.Column("build_ref", sa.String(length=26), nullable=True),
        sa.Column("status", BUILDSTATUS, nullable=False, server_default="queued"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_build_id"],
            ["configuration_builds.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("builds_workspace_idx", "builds", ["workspace_id"], unique=False)
    op.create_index("builds_config_idx", "builds", ["config_id"], unique=False)
    op.create_index("builds_status_idx", "builds", ["status"], unique=False)
    op.create_index("builds_build_ref_idx", "builds", ["build_ref"], unique=False)

    op.create_table(
        "build_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("build_id", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("stream", sa.String(length=20), nullable=False, server_default="stdout"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="CASCADE"),
    )
    op.create_index("build_logs_build_id_idx", "build_logs", ["build_id"], unique=False)
    op.create_index("build_logs_stream_idx", "build_logs", ["stream"], unique=False)


def downgrade() -> None:  # pragma: no cover - destructive downgrade
    op.drop_index("build_logs_stream_idx", table_name="build_logs")
    op.drop_index("build_logs_build_id_idx", table_name="build_logs")
    op.drop_table("build_logs")

    op.drop_index("builds_build_ref_idx", table_name="builds")
    op.drop_index("builds_status_idx", table_name="builds")
    op.drop_index("builds_config_idx", table_name="builds")
    op.drop_index("builds_workspace_idx", table_name="builds")
    op.drop_table("builds")

    bind = op.get_bind()
    BUILDSTATUS.drop(bind, checkfirst=True)

