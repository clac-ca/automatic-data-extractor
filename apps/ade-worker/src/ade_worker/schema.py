"""SQLAlchemy Core schema for the worker.

This is intentionally tiny and uses portable types so it works on:
- SQLite (local dev)
- SQL Server / Azure SQL (prod)

If your main application already owns these tables, keep their names/columns aligned.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

# ---- Domain tables (minimal fields used by worker) ----
builds = Table(
    "builds",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("fingerprint", String(128), nullable=False),

    Column("engine_spec", String(255), nullable=True),
    Column("python_interpreter", String(512), nullable=True),
    Column("python_version", String(50), nullable=True),
    Column("engine_version", String(50), nullable=True),
    Column("config_digest", String(80), nullable=True),

    Column("status", String(20), nullable=False),
    Column("exit_code", Integer, nullable=True),
    Column("summary", Text, nullable=True),
    Column("error_message", Text, nullable=True),

    Column("created_at", DateTime, nullable=False),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("build_id", String(36), nullable=True),
    Column("input_document_id", String(36), nullable=False),

    Column("input_sheet_names", Text, nullable=True),    # JSON text
    Column("run_options", Text, nullable=True),          # JSON text
    Column("output_path", String(512), nullable=True),

    Column("status", String(20), nullable=False),
    Column("available_at", DateTime, nullable=False),
    Column("attempt_count", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="3"),
    Column("claimed_by", String(255), nullable=True),
    Column("claim_expires_at", DateTime, nullable=True),

    Column("exit_code", Integer, nullable=True),
    Column("error_message", Text, nullable=True),

    Column("created_at", DateTime, nullable=False),
    Column("started_at", DateTime, nullable=True),
    Column("completed_at", DateTime, nullable=True),
)

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("original_filename", String(255), nullable=False),
    Column("stored_uri", String(512), nullable=False),   # typically file:<relative-path>
    Column("status", String(20), nullable=False),        # uploaded|processing|processed|failed
    Column("updated_at", DateTime, nullable=False),
)

REQUIRED_TABLES = ["builds", "runs", "documents"]

__all__ = ["metadata", "builds", "runs", "documents", "REQUIRED_TABLES"]
