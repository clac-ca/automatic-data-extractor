from __future__ import annotations

import io

import pytest

from ade_storage.azure_blob import AzureBlobConfig, AzureBlobStorage
from ade_storage.base import StorageError


class _DummyBlob:
    def __init__(self, result: dict[str, str] | None) -> None:
        self._result = result or {}

    def upload_blob(self, *_args, **_kwargs):
        return self._result


class _DummyContainer:
    def __init__(self, result: dict[str, str] | None) -> None:
        self._result = result

    def get_blob_client(self, *_args, **_kwargs):
        return _DummyBlob(self._result)


def _make_storage(prefix: str = "workspaces") -> AzureBlobStorage:
    cfg = AzureBlobConfig(
        account_url="https://example.blob.core.windows.net",
        connection_string=None,
        container="ade",
        prefix=prefix,
        require_versioning=True,
        request_timeout_seconds=30,
        max_concurrency=4,
        upload_chunk_size_bytes=4 * 1024 * 1024,
        download_chunk_size_bytes=1024 * 1024,
    )
    return AzureBlobStorage(cfg)


def test_blob_name_prefix_applied() -> None:
    storage = _make_storage(prefix="workspaces")
    assert storage._blob_name("files/abc") == "workspaces/files/abc"
    assert storage._blob_name("/files/abc") == "workspaces/files/abc"


def test_blob_name_no_prefix() -> None:
    storage = _make_storage(prefix="")
    assert storage._blob_name("files/abc") == "files/abc"


def test_require_versioning_raises_when_upload_has_no_version_id() -> None:
    storage = _make_storage()
    storage._container_client = _DummyContainer(result={})  # type: ignore[attr-defined]
    with pytest.raises(StorageError, match="version_id"):
        storage.write("files/abc", io.BytesIO(b"data"))


def test_require_versioning_allows_upload_with_version_id() -> None:
    storage = _make_storage()
    storage._container_client = _DummyContainer(result={"version_id": "v1"})  # type: ignore[attr-defined]
    stored = storage.write("files/abc", io.BytesIO(b"data"))
    assert stored.version_id == "v1"
