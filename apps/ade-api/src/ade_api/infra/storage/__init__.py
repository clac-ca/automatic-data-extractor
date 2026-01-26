"""Storage adapters and filesystem layout helpers."""

from __future__ import annotations

from .base import StorageAdapter, StorageError, StorageLimitError, StoredObject
from .azure_blob import AzureBlobConfig, AzureBlobStorage
from .factory import build_storage_adapter
from .layout import (
    workspace_config_root,
    workspace_documents_root,
    workspace_root,
    workspace_run_root,
    workspace_venvs_root,
)

__all__ = [
    "StorageAdapter",
    "StorageError",
    "StorageLimitError",
    "StoredObject",
    "AzureBlobConfig",
    "AzureBlobStorage",
    "build_storage_adapter",
    "workspace_config_root",
    "workspace_documents_root",
    "workspace_root",
    "workspace_run_root",
    "workspace_venvs_root",
]
