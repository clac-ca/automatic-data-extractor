"""Azure Blob storage adapter."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Iterator
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .base import StorageAdapter, StorageError, StorageLimitError, StoredObject

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
            raise StorageLimitError(limit=self._max_bytes, received=self._size)
        self._digest.update(chunk)
        return chunk

    @property
    def size(self) -> int:
        return self._size

    @property
    def digest(self) -> str:
        return self._digest.hexdigest()


class AzureBlobStorage(StorageAdapter):
    """Storage adapter backed by Azure Blob Storage."""

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
                raise StorageError(
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

    @property
    def config(self) -> AzureBlobConfig:
        return self._config

    def ensure_versioning(self) -> None:
        return

    def check_connection(self) -> None:
        try:
            self._container_client.get_container_properties()
        except ResourceNotFoundError as exc:
            raise StorageError("Blob container does not exist or is not accessible.") from exc
        except HttpResponseError as exc:
            raise StorageError("Failed to access blob container.") from exc

    def _blob_name(self, uri: str) -> str:
        name = uri.lstrip("/")
        if self._config.prefix:
            return f"{self._config.prefix}/{name}"
        return name

    def write(
        self,
        uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        blob_name = self._blob_name(uri)
        blob = self._container_client.get_blob_client(blob_name)

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
        except StorageLimitError:
            raise
        except HttpResponseError as exc:
            raise StorageError("Failed to upload blob") from exc

        version_id = result.get("version_id") if isinstance(result, dict) else None
        if self._config.require_versioning and not version_id:
            raise StorageError(
                "Blob versioning is required but no version_id was returned by upload. "
                "Verify blob versioning is enabled for this storage account."
            )

        return StoredObject(
            uri=uri,
            sha256=reader.digest,
            byte_size=reader.size,
            version_id=version_id,
        )

    def stream(
        self,
        uri: str,
        *,
        version_id: str | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        blob_name = self._blob_name(uri)
        blob = self._container_client.get_blob_client(blob_name, version_id=version_id)
        try:
            downloader = blob.download_blob(
                max_concurrency=self._config.max_concurrency,
                timeout=self._config.request_timeout_seconds,
            )
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(uri) from exc
        except HttpResponseError as exc:
            raise StorageError("Failed to download blob") from exc

        def _iter() -> Iterator[bytes]:
            while True:
                chunk = downloader.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        return _iter()

    def upload_path(self, uri: str, path: Path, *, max_bytes: int | None = None) -> StoredObject:
        with path.open("rb") as stream:
            return self.write(uri, stream, max_bytes=max_bytes)

    def download_to_path(
        self,
        uri: str,
        *,
        version_id: str | None,
        destination: Path,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as fh:
            for chunk in self.stream(uri, version_id=version_id):
                fh.write(chunk)

    def delete(self, uri: str, *, version_id: str | None = None) -> None:
        blob_name = self._blob_name(uri)
        blob = self._container_client.get_blob_client(blob_name, version_id=version_id)
        try:
            blob.delete_blob()
        except ResourceNotFoundError:
            return
        except HttpResponseError as exc:
            raise StorageError("Failed to delete blob") from exc

    def delete_prefix(self, prefix: str | None = None) -> int:
        normalized = (prefix or "").strip("/")
        name_starts_with = f"{normalized}/" if normalized else None
        include = ["versions"] if self._config.require_versioning else None
        deleted = 0
        for blob in self._container_client.list_blobs(
            name_starts_with=name_starts_with,
            include=include,
        ):
            version_id = getattr(blob, "version_id", None)
            blob_client = self._container_client.get_blob_client(
                blob.name,
                version_id=version_id,
            )
            try:
                blob_client.delete_blob()
            except ResourceNotFoundError:
                continue
            except HttpResponseError as exc:
                raise StorageError("Failed to delete blob") from exc
            else:
                deleted += 1
        return deleted


__all__ = ["AzureBlobConfig", "AzureBlobStorage"]
