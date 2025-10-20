"""Base interfaces for ADE storage adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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


class StorageAdapter(ABC):
    """Protocol implemented by storage adapters."""

    @abstractmethod
    async def write(
        self,
        uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        """Persist ``stream`` to ``uri`` returning a ``StoredObject`` descriptor."""

    @abstractmethod
    async def stream(self, uri: str, *, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
        """Yield the bytes stored at ``uri`` in ``chunk_size`` chunks."""

    @abstractmethod
    async def delete(self, uri: str) -> None:
        """Remove ``uri`` from storage if it exists."""
