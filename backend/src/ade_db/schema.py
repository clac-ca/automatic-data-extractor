"""SQLAlchemy Core schema access for shared ADE tables."""

from __future__ import annotations

from ade_db.metadata import Base
import ade_db.models  # noqa: F401

metadata = Base.metadata

# Expose common tables for SQLAlchemy Core usage (worker, tools, etc.).
environments = metadata.tables["environments"]
runs = metadata.tables["runs"]
files = metadata.tables["files"]
file_versions = metadata.tables["file_versions"]
run_metrics = metadata.tables["run_metrics"]
run_fields = metadata.tables["run_fields"]
run_table_columns = metadata.tables["run_table_columns"]

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
