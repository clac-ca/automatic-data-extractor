"""Document storage helpers built on ADE storage adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ade_api.infra.storage import (
    FilesystemStorage,
    StorageError,
    StorageLimitError,
    StoredObject,
)

from .exceptions import DocumentTooLargeError

_DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB default chunk size for streaming


@dataclass(slots=True)
class StoredDocument:
    """Metadata captured after writing a document to disk."""

    stored_uri: str
    sha256: str
    byte_size: int

    @classmethod
    def from_stored_object(cls, obj: StoredObject) -> StoredDocument:
        """Convert a storage adapter descriptor into a ``StoredDocument``."""

        return cls(stored_uri=obj.uri, sha256=obj.sha256, byte_size=obj.byte_size)


class DocumentStorage:
    """Confine file access to the configured documents directory."""

    def __init__(self, base_dir: Path, *, upload_prefix: str = "uploads") -> None:
        self._adapter = FilesystemStorage(base_dir, upload_prefix=upload_prefix)

    def make_stored_uri(self, document_id: str) -> str:
        """Return the canonical stored URI for ``document_id`` uploads."""

        return self._adapter.make_uri(document_id)

    def path_for(self, stored_uri: str) -> Path:
        """Return the absolute path for ``stored_uri`` within the documents directory."""

        # Normalise adapter-specific errors to ValueError for callers/tests.
        try:
            return self._adapter.path_for(stored_uri)
        except StorageError as exc:
            # Keep API surface predictable for higher-level features/tests which
            # assert ValueError on invalid storage URIs.
            raise ValueError(str(exc)) from exc

    async def write(
        self,
        stored_uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredDocument:
        """Persist ``stream`` to ``stored_uri`` returning metadata about the write."""

        try:
            stored = await self._adapter.write(stored_uri, stream, max_bytes=max_bytes)
        except StorageLimitError as exc:
            raise DocumentTooLargeError(limit=exc.limit, received=exc.received) from exc

        return StoredDocument.from_stored_object(stored)

    async def stream(
        self,
        stored_uri: str,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> AsyncIterator[bytes]:
        """Yield the bytes stored at ``stored_uri`` in ``chunk_size`` chunks."""

        async for chunk in self._adapter.stream(stored_uri, chunk_size=chunk_size):
            yield chunk

    async def delete(self, stored_uri: str) -> None:
        """Remove ``stored_uri`` from disk if it exists."""

        await self._adapter.delete(stored_uri)


__all__ = ["DocumentStorage", "StoredDocument"]
