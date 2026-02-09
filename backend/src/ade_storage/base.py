"""Base interfaces for ADE storage adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO


class StorageError(Exception):
    """Raised when a storage adapter encounters an unrecoverable error."""


class StorageLimitError(StorageError):
    """Raised when a storage write exceeds configured limits."""

    def __init__(self, *, limit: int, received: int) -> None:
        super().__init__(
            f"Object exceeds maximum size of {limit} bytes (received {received} bytes).",
        )
        self.limit = limit
        self.received = received


@dataclass(slots=True)
class StoredObject:
    """Metadata describing an object persisted by a storage adapter."""

    uri: str
    sha256: str
    byte_size: int
    version_id: str | None = None


class StorageAdapter(ABC):
    """Protocol implemented by storage adapters."""

    @abstractmethod
    def check_connection(self) -> None:
        """Raise StorageError if the storage backend is not accessible."""

    @abstractmethod
    def write(
        self,
        uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        """Persist ``stream`` to ``uri`` returning a ``StoredObject`` descriptor."""

    @abstractmethod
    def stream(
        self,
        uri: str,
        *,
        version_id: str | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        """Yield the bytes stored at ``uri`` (optionally pinned by version_id)."""

    @abstractmethod
    def stream_range(
        self,
        uri: str,
        *,
        start_offset: int = 0,
        version_id: str | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        """Yield bytes stored at ``uri`` starting at ``start_offset``."""

    @abstractmethod
    def delete(self, uri: str, *, version_id: str | None = None) -> None:
        """Remove ``uri`` from storage if it exists."""
