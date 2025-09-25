"""Add workspace settings column."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_workspace_settings"
down_revision = "0004_extracted_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    default = sa.text("'{}'::json")

    op.add_column(
        "workspaces",
        sa.Column(
            "settings",
            sa.JSON(),
            nullable=False,
            server_default=default,
        ),
    )
    op.execute(sa.text("UPDATE workspaces SET settings = '{}'::json WHERE settings IS NULL"))


def downgrade() -> None:
    op.drop_column("workspaces", "settings")
