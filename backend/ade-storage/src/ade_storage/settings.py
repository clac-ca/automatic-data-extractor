"""Protocol definitions for shared storage settings."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BlobStorageSettings(Protocol):
    blob_account_url: str | None
    blob_connection_string: str | None
    blob_container: str | None
    blob_prefix: str
    blob_require_versioning: bool
    blob_request_timeout_seconds: float
    blob_max_concurrency: int
    blob_upload_chunk_size_bytes: int
    blob_download_chunk_size_bytes: int


class StorageLayoutSettings(Protocol):
    workspaces_dir: Path
    configs_dir: Path
    runs_dir: Path
    documents_dir: Path
    venvs_dir: Path


__all__ = ["BlobStorageSettings", "StorageLayoutSettings"]
