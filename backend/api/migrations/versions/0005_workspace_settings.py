"""Add workspace settings column."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_workspace_settings"
down_revision = "0004_extracted_tables"
branch_labels = None
depends_on = None


def _server_default_for(dialect: str) -> sa.sql.elements.TextClause:
    if dialect == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("workspaces")}
    if "settings" in columns:
        bind.execute(
            sa.text("UPDATE workspaces SET settings = :value WHERE settings IS NULL"),
            {"value": "{}"},
        )
        return

    dialect = bind.dialect.name
    server_default = _server_default_for(dialect)

    op.add_column(
        "workspaces",
        sa.Column(
            "settings",
            sa.JSON(),
            nullable=False,
            server_default=server_default,
        ),
    )

    bind.execute(
        sa.text("UPDATE workspaces SET settings = :value WHERE settings IS NULL"),
        {"value": "{}"},
    )

    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE workspaces ALTER COLUMN settings DROP DEFAULT"))


def downgrade() -> None:
    op.drop_column("workspaces", "settings")
