"""Config engine v0.4 schema rewrite.

Revision ID: 0002_config_engine_v0_4
Revises: 0001_initial_schema
Create Date: 2025-10-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_config_engine_v0_4"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # configs -----------------------------------------------------------------
    with op.batch_alter_table("configs") as batch_op:
        batch_op.drop_constraint("configs_workspace_id_slug_key", type_="unique")
        batch_op.drop_constraint("configs_deleted_by_fkey", type_="foreignkey")
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'inactive'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "version",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'v1'"),
            )
        )
        batch_op.add_column(sa.Column("files_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("package_sha256", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("activated_by", sa.String(length=26), nullable=True)
        )
        batch_op.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("archived_by", sa.String(length=26), nullable=True))
        batch_op.drop_column("slug")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("deleted_by")
        batch_op.create_check_constraint(
            "configs_status_ck",
            "status IN ('active','inactive','archived')",
        )
        batch_op.create_foreign_key(
            "configs_activated_by_fkey",
            "users",
            ["activated_by"],
            ["user_id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "configs_archived_by_fkey",
            "users",
            ["archived_by"],
            ["user_id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "configs_active_unique_idx",
        "configs",
        ["workspace_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    # workspaces --------------------------------------------------------------
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("active_config_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "workspaces_active_config_id_fkey",
            "configs",
            ["active_config_id"],
            ["config_id"],
            ondelete="SET NULL",
        )

    # jobs --------------------------------------------------------------------
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("config_id", sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column("config_files_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("config_package_sha256", sa.String(length=64), nullable=True)
        )

    op.execute(
        """
        UPDATE jobs AS j
        SET
            config_id = cv.config_id,
            config_files_hash = cv.files_hash
        FROM config_versions AS cv
        WHERE cv.config_version_id = j.config_version_id
        """
    )

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("jobs_config_version_id_fkey", type_="foreignkey")
        batch_op.alter_column(
            "config_id",
            existing_type=sa.String(length=26),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "jobs_config_id_fkey",
            "configs",
            ["config_id"],
            ["config_id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("config_version_id")

    op.drop_table("config_files")
    op.drop_index("config_versions_active_unique_idx", table_name="config_versions")
    op.drop_table("config_versions")

    op.execute("UPDATE configs SET status = 'inactive' WHERE status IS NULL")
    op.execute("UPDATE configs SET version = 'v1' WHERE version IS NULL")

    with op.batch_alter_table("configs") as batch_op:
        batch_op.alter_column(
            "status",
            server_default=None,
            existing_type=sa.String(length=20),
        )
        batch_op.alter_column(
            "version",
            server_default=None,
            existing_type=sa.String(length=32),
        )


def downgrade() -> None:
    raise RuntimeError("Downgrade not supported for config engine v0.4 migration")
