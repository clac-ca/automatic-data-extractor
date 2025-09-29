"""Create system_settings table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_system_settings"
down_revision = "0005_workspace_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE system_settings ALTER COLUMN value DROP DEFAULT"))


def downgrade() -> None:
    op.drop_table("system_settings")
