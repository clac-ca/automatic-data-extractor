"""Local filesystem-backed storage adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

from fastapi.concurrency import run_in_threadpool

from .base import StorageAdapter, StorageError, StorageLimitError, StoredObject

_DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class FilesystemStorage(StorageAdapter):
    """Store objects on the local filesystem within a configured base directory."""

    def __init__(self, base_dir: Path, *, upload_prefix: str = "uploads") -> None:
        self._base_dir = Path(base_dir).expanduser().resolve()
        self._upload_prefix = upload_prefix.strip("/") or "uploads"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def make_uri(self, object_id: str) -> str:
        """Return a canonical storage URI for ``object_id``."""

        return f"{self._upload_prefix}/{object_id}"

    def path_for(self, uri: str) -> Path:
        """Return the absolute filesystem path for ``uri``."""

        relative = uri.lstrip("/")
        candidate = (self._base_dir / relative).resolve()
        try:
            candidate.relative_to(self._base_dir)
        except ValueError as exc:
            raise StorageError("Storage URI escapes the configured base directory.") from exc
        return candidate

    async def write(
        self,
        uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        """Persist ``stream`` to storage returning metadata about the write."""

        destination = self.path_for(uri)

        def _write() -> StoredObject:
            rewind = getattr(stream, "seek", None)
            if callable(rewind):
                try:
                    rewind(0)
                except (OSError, ValueError):
                    pass

            size = 0
            digest = sha256()
            destination.parent.mkdir(parents=True, exist_ok=True)

            success = False
            try:
                with destination.open("wb") as target:
                    while True:
                        chunk = stream.read(_DEFAULT_CHUNK_SIZE)
                        if not chunk:
                            break
                        size += len(chunk)
                        if max_bytes is not None and size > max_bytes:
                            raise StorageLimitError(limit=max_bytes, received=size)
                        target.write(chunk)
                        digest.update(chunk)
                success = True
            finally:
                if not success:
                    destination.unlink(missing_ok=True)

            return StoredObject(uri=uri, sha256=digest.hexdigest(), byte_size=size)

        return await run_in_threadpool(_write)

    async def stream(
        self,
        uri: str,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> AsyncIterator[bytes]:
        """Yield chunks for ``uri``."""

        path = self.path_for(uri)
        exists = await run_in_threadpool(path.exists)
        if not exists:
            raise FileNotFoundError(uri)

        with path.open("rb") as source:
            while True:
                chunk = await run_in_threadpool(source.read, chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, uri: str) -> None:
        """Delete ``uri`` if it exists."""

        path = self.path_for(uri)

        def _remove() -> None:
            try:
                path.unlink()
            except FileNotFoundError:
                return

        await run_in_threadpool(_remove)
