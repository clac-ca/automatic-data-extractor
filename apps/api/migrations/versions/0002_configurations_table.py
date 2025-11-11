"""Add configurations table for workspace config packages."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_configurations_table"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configurations",
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("config_id", sa.String(length=26), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "config_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id", "config_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "configurations_workspace_status_idx",
        "configurations",
        ["workspace_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("configurations_workspace_status_idx", table_name="configurations")
    op.drop_table("configurations")
