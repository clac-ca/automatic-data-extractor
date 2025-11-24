"""Retarget job FKs to configurations table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_jobs_config_fk"
previous = "0005_run_input_sheet_names"
down_revision = previous
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("configurations", recreate="always") as batch:
        batch.create_unique_constraint(
            "configurations_config_id_key",
            ["config_id"],
        )

    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.drop_constraint("jobs_config_id_fkey", type_="foreignkey")
        batch.drop_constraint("jobs_config_version_id_fkey", type_="foreignkey")
        batch.create_foreign_key(
            "jobs_config_id_fkey",
            "configurations",
            ["config_id"],
            ["config_id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "jobs_config_version_id_fkey",
            "configurations",
            ["config_version_id"],
            ["config_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("configurations", recreate="always") as batch:
        batch.drop_constraint(
            "configurations_config_id_key",
            type_="unique",
        )

    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.drop_constraint("jobs_config_id_fkey", type_="foreignkey")
        batch.drop_constraint("jobs_config_version_id_fkey", type_="foreignkey")
        batch.create_foreign_key(
            "jobs_config_id_fkey",
            "configs",
            ["config_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "jobs_config_version_id_fkey",
            "config_versions",
            ["config_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
