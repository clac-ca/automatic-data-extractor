"""Azure Blob helpers for the worker."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Iterator

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .settings import Settings

@dataclass(frozen=True, slots=True)
class AzureBlobConfig:
    account_url: str | None
    connection_string: str | None
    container: str
    prefix: str
    require_versioning: bool
    request_timeout_seconds: float
    max_concurrency: int
    upload_chunk_size_bytes: int
    download_chunk_size_bytes: int


@dataclass(frozen=True, slots=True)
class BlobWriteResult:
    blob_name: str
    sha256: str
    byte_size: int
    version_id: str | None


class _HashingReader:
    def __init__(self, stream: BinaryIO, *, max_bytes: int | None) -> None:
        self._stream = stream
        self._max_bytes = max_bytes
        self._size = 0
        self._digest = sha256()

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        if not chunk:
            return chunk
        self._size += len(chunk)
        if self._max_bytes is not None and self._size > self._max_bytes:
            raise ValueError(f"Object exceeds maximum size of {self._max_bytes} bytes")
        self._digest.update(chunk)
        return chunk

    @property
    def size(self) -> int:
        return self._size

    @property
    def digest(self) -> str:
        return self._digest.hexdigest()


class AzureBlobStorage:
    def __init__(self, config: AzureBlobConfig) -> None:
        self._config = config
        if config.connection_string:
            self._service = BlobServiceClient.from_connection_string(
                conn_str=config.connection_string,
                max_block_size=config.upload_chunk_size_bytes,
                max_chunk_get_size=config.download_chunk_size_bytes,
                max_single_get_size=config.download_chunk_size_bytes,
            )
        else:
            if not config.account_url:
                raise RuntimeError(
                    "Azure Blob account URL is required when no connection string is provided."
                )
            self._service = BlobServiceClient(
                account_url=config.account_url,
                credential=DefaultAzureCredential(),
                max_block_size=config.upload_chunk_size_bytes,
                max_chunk_get_size=config.download_chunk_size_bytes,
                max_single_get_size=config.download_chunk_size_bytes,
            )
        self._container_client = self._service.get_container_client(config.container)

    def _blob_name(self, name: str) -> str:
        trimmed = name.lstrip("/")
        if self._config.prefix:
            return f"{self._config.prefix}/{trimmed}"
        return trimmed

    def ensure_versioning(self) -> None:
        return

    def upload_stream(
        self,
        blob_name: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> BlobWriteResult:
        name = self._blob_name(blob_name)
        blob = self._container_client.get_blob_client(name)

        rewind = getattr(stream, "seek", None)
        if callable(rewind):
            try:
                rewind(0)
            except (OSError, ValueError):
                pass

        reader = _HashingReader(stream, max_bytes=max_bytes)
        try:
            result = blob.upload_blob(
                reader,
                overwrite=True,
                max_concurrency=self._config.max_concurrency,
                timeout=self._config.request_timeout_seconds,
            )
        except HttpResponseError as exc:
            raise RuntimeError("Failed to upload blob") from exc
        version_id = result.get("version_id") if isinstance(result, dict) else None
        if self._config.require_versioning and not version_id:
            raise RuntimeError(
                "Blob versioning is required but no version_id was returned by upload. "
                "Verify blob versioning is enabled for this storage account."
            )

        return BlobWriteResult(
            blob_name=name,
            sha256=reader.digest,
            byte_size=reader.size,
            version_id=version_id,
        )

    def upload_path(self, blob_name: str, path: Path) -> BlobWriteResult:
        with path.open("rb") as stream:
            return self.upload_stream(blob_name, stream)

    def stream(
        self,
        blob_name: str,
        *,
        version_id: str | None = None,
    ) -> Iterator[bytes]:
        name = self._blob_name(blob_name)
        blob = self._container_client.get_blob_client(name, version_id=version_id)
        downloader = blob.download_blob(
            max_concurrency=self._config.max_concurrency,
            timeout=self._config.request_timeout_seconds,
        )
        for chunk in downloader.chunks():
            yield chunk

    def download_to_path(
        self,
        blob_name: str,
        *,
        version_id: str | None,
        destination: Path,
    ) -> None:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as fh:
                for chunk in self.stream(blob_name, version_id=version_id):
                    fh.write(chunk)
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(blob_name) from exc
        except HttpResponseError as exc:
            raise RuntimeError("Failed to download blob") from exc


def build_storage(settings: Settings) -> AzureBlobStorage:
    config = AzureBlobConfig(
        account_url=settings.blob_account_url,
        connection_string=settings.blob_connection_string,
        container=settings.blob_container or "",
        prefix=settings.blob_prefix,
        require_versioning=settings.blob_require_versioning,
        request_timeout_seconds=float(settings.blob_request_timeout_seconds),
        max_concurrency=int(settings.blob_max_concurrency),
        upload_chunk_size_bytes=int(settings.blob_upload_chunk_size_bytes),
        download_chunk_size_bytes=int(settings.blob_download_chunk_size_bytes),
    )
    storage = AzureBlobStorage(config)
    storage.ensure_versioning()
    return storage


__all__ = [
    "AzureBlobConfig",
    "AzureBlobStorage",
    "BlobWriteResult",
    "build_storage",
]
