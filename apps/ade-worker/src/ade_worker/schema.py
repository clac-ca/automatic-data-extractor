"""SQLAlchemy table definitions used by ade-worker."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("build_id", String(36), nullable=True),
    Column("input_document_id", String(36), nullable=False),
    Column("run_options", JSON, nullable=True),
    Column("input_sheet_names", JSON, nullable=True),
    Column("available_at", DateTime, nullable=False),
    Column("attempt_count", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("claimed_by", String(255), nullable=True),
    Column("claim_expires_at", DateTime, nullable=True),
    Column("status", String(20), nullable=False),
    Column("exit_code", Integer, nullable=True),
    Column("submitted_by_user_id", String(36), nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("started_at", DateTime, nullable=True),
    Column("completed_at", DateTime, nullable=True),
    Column("cancelled_at", DateTime, nullable=True),
    Column("error_message", Text, nullable=True),
)

builds = Table(
    "builds",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("fingerprint", String(128), nullable=False),
    Column("engine_spec", String(255), nullable=True),
    Column("engine_version", String(50), nullable=True),
    Column("python_version", String(50), nullable=True),
    Column("python_interpreter", String(255), nullable=True),
    Column("config_digest", String(80), nullable=True),
    Column("status", String(20), nullable=False),
    Column("exit_code", Integer, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
    Column("summary", Text, nullable=True),
    Column("error_message", Text, nullable=True),
)

configurations = Table(
    "configurations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("active_build_id", String(36), nullable=True),
    Column("active_build_fingerprint", String(128), nullable=True),
    Column("status", String(20), nullable=False),
)

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("original_filename", String(255), nullable=False),
    Column("content_type", String(255), nullable=True),
    Column("byte_size", Integer, nullable=False),
    Column("stored_uri", String(512), nullable=False),
    Column("status", String(20), nullable=False),
    Column("last_run_at", DateTime, nullable=True),
)

run_metrics = Table(
    "run_metrics",
    metadata,
    Column("run_id", String(36), primary_key=True),
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
    Column("run_id", String(36), primary_key=True),
    Column("field", String(128), primary_key=True),
    Column("label", String(255), nullable=True),
    Column("detected", Boolean, nullable=False),
    Column("best_mapping_score", Float, nullable=True),
    Column("occurrences_tables", Integer, nullable=False),
    Column("occurrences_columns", Integer, nullable=False),
)

run_table_columns = Table(
    "run_table_columns",
    metadata,
    Column("run_id", String(36), primary_key=True),
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
)

