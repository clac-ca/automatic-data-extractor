"""Add workspace ownership to core resources."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007_workspace_owned_resources"
down_revision = "0006_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    for table in ("extracted_tables", "jobs", "documents", "configurations"):
        conn.execute(sa.text(f"DELETE FROM {table}"))

    with op.batch_alter_table("configurations") as batch_op:
        batch_op.drop_index("configurations_document_type_active_idx")
        batch_op.drop_constraint(
            "configurations_document_type_version_key",
            type_="unique",
        )
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "configurations_workspace_id_fkey",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="CASCADE",
        )

    op.alter_column("configurations", "workspace_id", nullable=False)
    op.create_unique_constraint(
        "configurations_workspace_document_type_version_key",
        "configurations",
        ["workspace_id", "document_type", "version"],
    )
    op.create_index(
        "configurations_workspace_active_idx",
        "configurations",
        ["workspace_id", "document_type"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
    )

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "documents_workspace_id_fkey",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="CASCADE",
        )

    op.alter_column("documents", "workspace_id", nullable=False)
    op.create_index("documents_workspace_id_idx", "documents", ["workspace_id"], unique=False)

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "jobs_workspace_id_fkey",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="CASCADE",
        )

    op.alter_column("jobs", "workspace_id", nullable=False)
    op.create_index("jobs_workspace_id_idx", "jobs", ["workspace_id"], unique=False)

    with op.batch_alter_table("extracted_tables") as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "extracted_tables_workspace_id_fkey",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="CASCADE",
        )

    op.alter_column("extracted_tables", "workspace_id", nullable=False)
    op.create_index(
        "extracted_tables_workspace_id_idx",
        "extracted_tables",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("extracted_tables_workspace_id_idx", table_name="extracted_tables")
    with op.batch_alter_table("extracted_tables") as batch_op:
        batch_op.drop_constraint("extracted_tables_workspace_id_fkey", type_="foreignkey")
        batch_op.drop_column("workspace_id")

    op.drop_index("jobs_workspace_id_idx", table_name="jobs")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("jobs_workspace_id_fkey", type_="foreignkey")
        batch_op.drop_column("workspace_id")

    op.drop_index("documents_workspace_id_idx", table_name="documents")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("documents_workspace_id_fkey", type_="foreignkey")
        batch_op.drop_column("workspace_id")

    op.drop_index("configurations_workspace_active_idx", table_name="configurations")
    op.drop_constraint(
        "configurations_workspace_document_type_version_key",
        "configurations",
        type_="unique",
    )
    with op.batch_alter_table("configurations") as batch_op:
        batch_op.drop_constraint("configurations_workspace_id_fkey", type_="foreignkey")
        batch_op.drop_column("workspace_id")
        batch_op.create_unique_constraint(
            "configurations_document_type_version_key",
            ["document_type", "version"],
        )
        batch_op.create_index(
            "configurations_document_type_active_idx",
            ["document_type"],
            unique=True,
            sqlite_where=sa.text("is_active = 1"),
        )
