"""Storage adapter factory + FastAPI lifecycle helpers."""

from __future__ import annotations

from fastapi import FastAPI, Request, WebSocket

from ade_api.settings import Settings

from .azure_blob import AzureBlobConfig, AzureBlobStorage


def build_storage_adapter(settings: Settings) -> AzureBlobStorage:
    config = AzureBlobConfig(
        account_url=settings.blob_account_url,
        connection_string=settings.blob_connection_string,
        container=settings.blob_container or "",
        prefix=settings.blob_prefix,
        require_versioning=settings.blob_require_versioning,
        request_timeout_seconds=settings.blob_request_timeout_seconds,
        max_concurrency=settings.blob_max_concurrency,
        upload_chunk_size_bytes=settings.blob_upload_chunk_size_bytes,
        download_chunk_size_bytes=settings.blob_download_chunk_size_bytes,
    )
    adapter = AzureBlobStorage(config)
    adapter.ensure_versioning()
    return adapter


def _resolve_app(app_or_request: FastAPI | Request | WebSocket) -> FastAPI:
    if isinstance(app_or_request, FastAPI):
        return app_or_request
    return app_or_request.app


def init_storage(app: FastAPI, settings: Settings) -> None:
    adapter = build_storage_adapter(settings)
    app.state.blob_storage = adapter


def shutdown_storage(app: FastAPI) -> None:
    app.state.blob_storage = None


def get_storage_adapter(app_or_request: FastAPI | Request | WebSocket) -> AzureBlobStorage:
    app = _resolve_app(app_or_request)
    adapter = getattr(app.state, "blob_storage", None)
    if adapter is None:
        raise RuntimeError("Storage not initialized. Call init_storage(app, ...) at startup.")
    return adapter


__all__ = [
    "build_storage_adapter",
    "get_storage_adapter",
    "init_storage",
    "shutdown_storage",
]
