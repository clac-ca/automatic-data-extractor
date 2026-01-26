"""Storage adapter factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ade_api.settings import Settings

from .filesystem import FilesystemStorage

if TYPE_CHECKING:
    from .azure_blob import AzureBlobConfig, AzureBlobStorage


def _load_azure() -> tuple[type, type]:
    try:
        from .azure_blob import AzureBlobConfig, AzureBlobStorage
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Azure Blob dependencies are not installed. Install azure-identity and "
            "azure-storage-blob to use ADE_STORAGE_BACKEND=azure_blob."
        ) from exc
    return AzureBlobConfig, AzureBlobStorage


def build_storage_adapter(settings: Settings) -> FilesystemStorage | AzureBlobStorage:
    if settings.storage_backend == "filesystem":
        return FilesystemStorage(Path(settings.documents_dir))

    AzureBlobConfig, AzureBlobStorage = _load_azure()
    config = AzureBlobConfig(
        account_url=settings.blob_account_url,
        connection_string=settings.blob_connection_string,
        container=settings.blob_container or "",
        prefix=settings.blob_prefix,
        require_versioning=settings.blob_require_versioning,
        create_container_on_startup=settings.blob_create_container_on_startup,
        request_timeout_seconds=settings.blob_request_timeout_seconds,
        max_concurrency=settings.blob_max_concurrency,
        upload_chunk_size_bytes=settings.blob_upload_chunk_size_bytes,
        download_chunk_size_bytes=settings.blob_download_chunk_size_bytes,
    )
    adapter = AzureBlobStorage(config)
    adapter.ensure_container()
    adapter.ensure_versioning()
    return adapter


__all__ = ["build_storage_adapter"]
