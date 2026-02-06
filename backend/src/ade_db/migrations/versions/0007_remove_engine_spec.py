"""Remove legacy engine_spec columns from runs/environments."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0007_remove_engine_spec"
down_revision: Optional[str] = "0006_document_history_simplify"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def _refresh_unique_columns(bind, table_name: str, constraint_name: str) -> tuple[str, ...] | None:
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("name") == constraint_name:
            columns = constraint.get("column_names") or []
            return tuple(str(column) for column in columns)
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    run_columns = {column["name"] for column in inspector.get_columns("runs")}
    env_columns = {column["name"] for column in inspector.get_columns("environments")}
    unique_columns = _refresh_unique_columns(bind, "environments", "ux_environments_key")

    expected_unique = ("workspace_id", "configuration_id", "deps_digest")
    if unique_columns is not None and unique_columns != expected_unique:
        op.drop_constraint("ux_environments_key", "environments", type_="unique")

    if "engine_spec" in run_columns:
        op.drop_column("runs", "engine_spec")
    if "engine_spec" in env_columns:
        op.drop_column("environments", "engine_spec")

    if _refresh_unique_columns(bind, "environments", "ux_environments_key") is None:
        op.create_unique_constraint(
            "ux_environments_key",
            "environments",
            ["workspace_id", "configuration_id", "deps_digest"],
        )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
