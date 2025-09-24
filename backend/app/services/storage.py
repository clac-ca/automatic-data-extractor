"""Filesystem storage helpers used across ADE services."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import AsyncIterator, BinaryIO

from fastapi.concurrency import run_in_threadpool

from ..modules.documents.exceptions import DocumentTooLargeError

_CHUNK_SIZE = 1024 * 1024  # 1 MiB default chunk size for streaming


@dataclass(slots=True)
class StoredDocument:
    """Metadata captured after writing a document to disk."""

    stored_uri: str
    sha256: str
    byte_size: int


class DocumentStorage:
    """Confine file access to the configured documents directory."""

    def __init__(self, base_dir: Path, *, upload_prefix: str = "uploads") -> None:
        self._base_dir = base_dir.resolve()
        self._upload_prefix = upload_prefix.strip("/") or "uploads"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def make_stored_uri(self, document_id: str) -> str:
        """Return the canonical stored URI for ``document_id`` uploads."""

        return f"{self._upload_prefix}/{document_id}"

    def path_for(self, stored_uri: str) -> Path:
        """Return the absolute path for ``stored_uri`` within ``base_dir``."""

        relative = stored_uri.lstrip("/")
        candidate = (self._base_dir / relative).resolve()
        try:
            candidate.relative_to(self._base_dir)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Stored URI escapes the documents directory") from exc
        return candidate

    async def write(
        self,
        stored_uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredDocument:
        """Persist ``stream`` to ``stored_uri`` returning metadata about the write."""

        destination = self.path_for(stored_uri)

        def _write() -> StoredDocument:
            try:
                stream.seek(0)
            except (AttributeError, OSError):  # pragma: no cover - best effort rewind
                pass

            size = 0
            digest = sha256()
            destination.parent.mkdir(parents=True, exist_ok=True)

            try:
                with destination.open("wb") as target:
                    while True:
                        chunk = stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        size += len(chunk)
                        if max_bytes is not None and size > max_bytes:
                            raise DocumentTooLargeError(limit=max_bytes, received=size)
                        target.write(chunk)
                        digest.update(chunk)
            except Exception:
                destination.unlink(missing_ok=True)
                raise

            return StoredDocument(
                stored_uri=stored_uri,
                sha256=digest.hexdigest(),
                byte_size=size,
            )

        return await run_in_threadpool(_write)

    async def stream(
        self,
        stored_uri: str,
        *,
        chunk_size: int = _CHUNK_SIZE,
    ) -> AsyncIterator[bytes]:
        """Yield the bytes stored at ``stored_uri`` in ``chunk_size`` chunks."""

        path = self.path_for(stored_uri)
        exists = await run_in_threadpool(path.exists)
        if not exists:
            raise FileNotFoundError(stored_uri)

        with path.open("rb") as source:
            while True:
                chunk = await run_in_threadpool(source.read, chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, stored_uri: str) -> None:
        """Remove ``stored_uri`` from disk if it exists."""

        path = self.path_for(stored_uri)

        def _remove() -> None:
            try:
                path.unlink()
            except FileNotFoundError:  # pragma: no cover - defensive cleanup
                return

        await run_in_threadpool(_remove)


__all__ = ["DocumentStorage", "StoredDocument"]
