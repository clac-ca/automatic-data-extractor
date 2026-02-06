"""Storage adapters and filesystem layout helpers."""

from __future__ import annotations

from .azure_blob import AzureBlobConfig, AzureBlobStorage
from .base import StorageAdapter, StorageError, StorageLimitError, StoredObject
from .factory import build_storage_adapter, get_storage_adapter, init_storage, shutdown_storage
from .layout import (
    ensure_storage_roots,
    storage_roots,
    workspace_config_root,
    workspace_documents_root,
    workspace_root,
    workspace_run_root,
    workspace_venvs_root,
)
from .settings import (
    BlobStorageSettings,
    Settings,
    StorageLayoutSettings,
    StorageSettings,
    get_settings,
    reload_settings,
)

__all__ = [
    "StorageAdapter",
    "StorageError",
    "StorageLimitError",
    "StoredObject",
    "AzureBlobConfig",
    "AzureBlobStorage",
    "build_storage_adapter",
    "get_storage_adapter",
    "init_storage",
    "shutdown_storage",
    "BlobStorageSettings",
    "Settings",
    "StorageLayoutSettings",
    "StorageSettings",
    "get_settings",
    "reload_settings",
    "ensure_storage_roots",
    "storage_roots",
    "workspace_config_root",
    "workspace_documents_root",
    "workspace_root",
    "workspace_run_root",
    "workspace_venvs_root",
]
