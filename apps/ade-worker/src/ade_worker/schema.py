"""SQLAlchemy Core schema for the worker (Postgres).

If your main application already owns these tables, keep their names/columns aligned.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

metadata = MetaData()

UUID_TYPE = PG_UUID(as_uuid=True)
TS = DateTime(timezone=True)

# ---- Domain tables (minimal fields used by worker) ----
environments = Table(
    "environments",
    metadata,
    Column("id", UUID_TYPE, primary_key=True),
    Column("workspace_id", UUID_TYPE, nullable=False),
    Column("configuration_id", UUID_TYPE, nullable=False),
    Column("engine_spec", String(255), nullable=False),
    Column("deps_digest", String(128), nullable=False),
    Column("status", String(20), nullable=False),
    Column("error_message", Text, nullable=True),
    Column("created_at", TS, nullable=False),
    Column("updated_at", TS, nullable=False),
    Column("last_used_at", TS, nullable=True),
    Column("python_version", String(50), nullable=True),
    Column("python_interpreter", String(512), nullable=True),
    Column("engine_version", String(50), nullable=True),
    UniqueConstraint(
        "workspace_id",
        "configuration_id",
        "engine_spec",
        "deps_digest",
        name="ux_environments_key",
    ),
    Index("ix_environments_claim", "status", "created_at"),
    Index("ix_environments_status_last_used", "status", "last_used_at"),
    Index("ix_environments_status_updated", "status", "updated_at"),
)

runs = Table(
    "runs",
    metadata,
    Column("id", UUID_TYPE, primary_key=True),
    Column("workspace_id", UUID_TYPE, nullable=False),
    Column("configuration_id", UUID_TYPE, nullable=False),
    Column("input_file_version_id", UUID_TYPE, nullable=False),
    Column("output_file_version_id", UUID_TYPE, nullable=True),

    Column("input_sheet_names", JSONB, nullable=True),
    Column("run_options", JSONB, nullable=True),
    Column("engine_spec", String(255), nullable=False),
    Column("deps_digest", String(128), nullable=False),

    Column("status", String(20), nullable=False),
    Column("available_at", TS, nullable=False),
    Column("attempt_count", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="3"),
    Column("claimed_by", String(255), nullable=True),
    Column("claim_expires_at", TS, nullable=True),

    Column("exit_code", Integer, nullable=True),
    Column("error_message", Text, nullable=True),

    Column("created_at", TS, nullable=False),
    Column("started_at", TS, nullable=True),
    Column("completed_at", TS, nullable=True),
    Index("ix_runs_claim", "status", "available_at", "created_at"),
    Index("ix_runs_status_created_at", "status", "created_at"),
    Index("ix_runs_claim_expires", "status", "claim_expires_at"),
    Index("ix_runs_status_completed", "status", "completed_at"),
)

files = Table(
    "files",
    metadata,
    Column("id", UUID_TYPE, primary_key=True),
    Column("workspace_id", UUID_TYPE, nullable=False),
    Column("kind", String(50), nullable=False),
    Column("doc_no", Integer, nullable=True),
    Column("name", String(255), nullable=False),
    Column("name_key", String(255), nullable=False),
    Column("blob_name", String(512), nullable=False),
    Column("current_version_id", UUID_TYPE, nullable=True),
    Column("parent_file_id", UUID_TYPE, nullable=True),
    Column("comment_count", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("attributes", JSONB, nullable=False),
    Column("uploaded_by_user_id", UUID_TYPE, nullable=True),
    Column("assignee_user_id", UUID_TYPE, nullable=True),
    Column("expires_at", TS, nullable=False),
    Column("last_run_id", UUID_TYPE, nullable=True),
    Column("deleted_at", TS, nullable=True),
    Column("deleted_by_user_id", UUID_TYPE, nullable=True),
    Column("created_at", TS, nullable=False),
    Column("updated_at", TS, nullable=False),
)

file_versions = Table(
    "file_versions",
    metadata,
    Column("id", UUID_TYPE, primary_key=True),
    Column("file_id", UUID_TYPE, nullable=False),
    Column("version_no", Integer, nullable=False),
    Column("origin", String(50), nullable=False),
    Column("run_id", UUID_TYPE, nullable=True),
    Column("created_by_user_id", UUID_TYPE, nullable=True),
    Column("sha256", String(64), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("content_type", String(255), nullable=True),
    Column("filename_at_upload", String(255), nullable=False),
    Column("blob_version_id", String(128), nullable=False),
    Column("created_at", TS, nullable=False),
    Column("updated_at", TS, nullable=False),
)

run_metrics = Table(
    "run_metrics",
    metadata,
    Column("run_id", UUID_TYPE, primary_key=True),
    Column("evaluation_outcome", String(20), nullable=True),
    Column("evaluation_findings_total", Integer, nullable=True),
    Column("evaluation_findings_info", Integer, nullable=True),
    Column("evaluation_findings_warning", Integer, nullable=True),
    Column("evaluation_findings_error", Integer, nullable=True),
    Column("validation_issues_total", Integer, nullable=True),
    Column("validation_issues_info", Integer, nullable=True),
    Column("validation_issues_warning", Integer, nullable=True),
    Column("validation_issues_error", Integer, nullable=True),
    Column("validation_max_severity", String(10), nullable=True),
    Column("workbook_count", Integer, nullable=True),
    Column("sheet_count", Integer, nullable=True),
    Column("table_count", Integer, nullable=True),
    Column("row_count_total", Integer, nullable=True),
    Column("row_count_empty", Integer, nullable=True),
    Column("column_count_total", Integer, nullable=True),
    Column("column_count_empty", Integer, nullable=True),
    Column("column_count_mapped", Integer, nullable=True),
    Column("column_count_unmapped", Integer, nullable=True),
    Column("field_count_expected", Integer, nullable=True),
    Column("field_count_detected", Integer, nullable=True),
    Column("field_count_not_detected", Integer, nullable=True),
    Column("cell_count_total", Integer, nullable=True),
    Column("cell_count_non_empty", Integer, nullable=True),
)

run_fields = Table(
    "run_fields",
    metadata,
    Column("run_id", UUID_TYPE, primary_key=True),
    Column("field", String(128), primary_key=True),
    Column("label", String(255), nullable=True),
    Column("detected", Boolean, nullable=False),
    Column("best_mapping_score", Float, nullable=True),
    Column("occurrences_tables", Integer, nullable=False),
    Column("occurrences_columns", Integer, nullable=False),
    Index("ix_run_fields_run", "run_id"),
    Index("ix_run_fields_field", "field"),
)

run_table_columns = Table(
    "run_table_columns",
    metadata,
    Column("run_id", UUID_TYPE, primary_key=True),
    Column("workbook_index", Integer, primary_key=True),
    Column("workbook_name", String(255), nullable=False),
    Column("sheet_index", Integer, primary_key=True),
    Column("sheet_name", String(255), nullable=False),
    Column("table_index", Integer, primary_key=True),
    Column("column_index", Integer, primary_key=True),
    Column("header_raw", Text, nullable=True),
    Column("header_normalized", Text, nullable=True),
    Column("non_empty_cells", Integer, nullable=False),
    Column("mapping_status", String(32), nullable=False),
    Column("mapped_field", String(128), nullable=True),
    Column("mapping_score", Float, nullable=True),
    Column("mapping_method", String(32), nullable=True),
    Column("unmapped_reason", String(64), nullable=True),
    Index("ix_run_table_columns_run", "run_id"),
    Index("ix_run_table_columns_run_sheet", "run_id", "sheet_name"),
    Index("ix_run_table_columns_run_mapped_field", "run_id", "mapped_field"),
)

REQUIRED_TABLES = [
    "environments",
    "runs",
    "files",
    "file_versions",
    "run_metrics",
    "run_fields",
    "run_table_columns",
]


__all__ = [
    "metadata",
    "environments",
    "runs",
    "files",
    "file_versions",
    "run_metrics",
    "run_fields",
    "run_table_columns",
    "REQUIRED_TABLES",
]
