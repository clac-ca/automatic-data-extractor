"""Add extracted tables for job outputs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_extracted_tables"
down_revision = "0003_service_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extracted_tables",
        sa.Column("table_id", sa.String(length=26), nullable=False),
        sa.Column("job_id", sa.String(length=40), nullable=False),
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("sample_rows", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("table_id"),
    )
    op.create_index(
        "extracted_tables_job_id_idx",
        "extracted_tables",
        ["job_id"],
    )
    op.create_index(
        "extracted_tables_document_id_idx",
        "extracted_tables",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("extracted_tables_document_id_idx", table_name="extracted_tables")
    op.drop_index("extracted_tables_job_id_idx", table_name="extracted_tables")
    op.drop_table("extracted_tables")
