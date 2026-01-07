"""SQLAlchemy Core schema for the worker.

This is intentionally tiny and uses portable types so it works on:
- SQLite (local dev)
- SQL Server / Azure SQL (prod)

If your main application already owns these tables, keep their names/columns aligned.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Index,
    UniqueConstraint,
)

metadata = MetaData()

# ---- Domain tables (minimal fields used by worker) ----
environments = Table(
    "environments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("engine_spec", String(255), nullable=False),
    Column("deps_digest", String(128), nullable=False),
    Column("status", String(20), nullable=False),
    Column("error_message", Text, nullable=True),
    Column("claimed_by", String(255), nullable=True),
    Column("claim_expires_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("last_used_at", DateTime, nullable=True),
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
    Index("ix_environments_claim_expires", "status", "claim_expires_at"),
    Index("ix_environments_status_last_used", "status", "last_used_at"),
    Index("ix_environments_status_updated", "status", "updated_at"),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("configuration_id", String(36), nullable=False),
    Column("input_document_id", String(36), nullable=False),

    Column("input_sheet_names", Text, nullable=True),    # JSON text
    Column("run_options", Text, nullable=True),          # JSON text
    Column("output_path", String(512), nullable=True),
    Column("engine_spec", String(255), nullable=False),
    Column("deps_digest", String(128), nullable=False),

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
    Index("ix_runs_claim", "status", "available_at", "created_at"),
    Index("ix_runs_claim_expires", "status", "claim_expires_at"),
    Index("ix_runs_status_completed", "status", "completed_at"),
)

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("workspace_id", String(36), nullable=False),
    Column("original_filename", String(255), nullable=False),
    Column("stored_uri", String(512), nullable=False),   # typically file:<relative-path>
    Column("status", String(20), nullable=False),        # uploaded|processing|processed|failed
    Column("version", Integer, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

document_events = Table(
    "document_events",
    metadata,
    Column("cursor", BigInteger, primary_key=True, autoincrement=True),
    Column("workspace_id", String(36), nullable=False),
    Column("document_id", String(36), nullable=False),
    Column("event_type", String(40), nullable=False),
    Column("document_version", Integer, nullable=False),
    Column("request_id", String(128), nullable=True),
    Column("client_request_id", String(128), nullable=True),
    Column("payload", Text, nullable=True),
    Column("occurred_at", DateTime, nullable=False),
    Index("ix_document_events_workspace_cursor", "workspace_id", "cursor"),
    Index("ix_document_events_workspace_document", "workspace_id", "document_id"),
    Index("ix_document_events_workspace_occurred", "workspace_id", "occurred_at"),
)

REQUIRED_TABLES = ["environments", "runs", "documents", "document_events"]

__all__ = ["metadata", "environments", "runs", "documents", "document_events", "REQUIRED_TABLES"]
