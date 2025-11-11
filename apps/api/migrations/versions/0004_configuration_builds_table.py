"""Create configuration_builds table for virtual environment tracking."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_configuration_builds_table"
down_revision = "0003_configuration_digest_and_active_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuration_builds",
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("build_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("venv_path", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=True),
        sa.Column("content_digest", sa.String(length=128), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "config_id", "build_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "config_id"],
            ["configurations.workspace_id", "configurations.config_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status in ('building','active','inactive','failed')",
            name="configuration_builds_status_check",
        ),
    )
    op.create_index(
        "configuration_builds_active_idx",
        "configuration_builds",
        ["workspace_id", "config_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "configuration_builds_building_idx",
        "configuration_builds",
        ["workspace_id", "config_id"],
        unique=True,
        sqlite_where=sa.text("status = 'building'"),
        postgresql_where=sa.text("status = 'building'"),
    )


def downgrade() -> None:
    op.drop_index("configuration_builds_building_idx", table_name="configuration_builds")
    op.drop_index("configuration_builds_active_idx", table_name="configuration_builds")
    op.drop_table("configuration_builds")
