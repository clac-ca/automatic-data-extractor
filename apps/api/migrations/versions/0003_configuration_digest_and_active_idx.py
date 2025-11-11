"""Add content digest and unique active constraint."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_configuration_digest_and_active_idx"
down_revision = "0002_configurations_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configurations",
        sa.Column("content_digest", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "configurations_workspace_active_unique",
        "configurations",
        ["workspace_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "configurations_workspace_active_unique",
        table_name="configurations",
    )
    op.drop_column("configurations", "content_digest")
