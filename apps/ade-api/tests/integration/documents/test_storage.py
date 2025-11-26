"""Document storage helper tests."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ade_api.features.documents import DocumentStorage
from ade_api.features.documents.exceptions import DocumentTooLargeError

pytestmark = pytest.mark.asyncio


async def test_path_resolution_prevents_escape(tmp_path: Path) -> None:
    """Stored URIs must not allow directory traversal outside the base."""

    storage = DocumentStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.path_for("../evil.txt")


async def test_write_and_stream_roundtrip(tmp_path: Path) -> None:
    """Writing a document should persist bytes and allow streaming reads."""

    storage = DocumentStorage(tmp_path)
    payload = b"0123456789" * 5
    stored_uri = storage.make_stored_uri("doc")

    result = await storage.write(stored_uri, io.BytesIO(payload))

    assert result.byte_size == len(payload)
    assert result.sha256
    path = storage.path_for(stored_uri)
    assert path.exists()

    streamed: list[bytes] = []
    async for chunk in storage.stream(stored_uri, chunk_size=7):
        streamed.append(chunk)

    assert b"".join(streamed) == payload


async def test_write_enforces_size_limit(tmp_path: Path) -> None:
    """DocumentStorage should raise when payload exceeds the configured limit."""

    storage = DocumentStorage(tmp_path)
    stored_uri = storage.make_stored_uri("too-big")

    with pytest.raises(DocumentTooLargeError):
        await storage.write(stored_uri, io.BytesIO(b"abcdef"), max_bytes=4)

    path = storage.path_for(stored_uri)
    assert not path.exists()


async def test_delete_removes_file(tmp_path: Path) -> None:
    """Deleting a stored URI should remove it from disk."""

    storage = DocumentStorage(tmp_path)
    stored_uri = storage.make_stored_uri("delete-me")

    await storage.write(stored_uri, io.BytesIO(b"payload"))
    path = storage.path_for(stored_uri)
    assert path.exists()

    await storage.delete(stored_uri)
    assert not path.exists()

