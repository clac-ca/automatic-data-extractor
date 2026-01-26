"""Storage adapters and filesystem layout helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import StorageAdapter, StorageError, StorageLimitError, StoredObject
from .filesystem import FilesystemStorage
from .factory import build_storage_adapter
from .layout import (
    workspace_config_root,
    workspace_documents_root,
    workspace_root,
    workspace_run_root,
    workspace_venvs_root,
)

if TYPE_CHECKING:
    from .azure_blob import AzureBlobConfig, AzureBlobStorage


def __getattr__(name: str):
    if name in {"AzureBlobConfig", "AzureBlobStorage"}:
        try:
            from .azure_blob import AzureBlobConfig, AzureBlobStorage
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Azure Blob dependencies are not installed. Install azure-identity and "
                "azure-storage-blob to use ADE_STORAGE_BACKEND=azure_blob."
            ) from exc
        return AzureBlobConfig if name == "AzureBlobConfig" else AzureBlobStorage
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "FilesystemStorage",
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
