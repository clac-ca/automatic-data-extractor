from __future__ import annotations

import io
from uuid import uuid4

from ade_api.infra.storage import build_storage_adapter
from ade_api.settings import Settings


def test_blob_storage_roundtrip() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_require_versioning=False,
        blob_create_container_on_startup=True,
        secret_key="test-secret-key-for-tests-please-change",
    )

    storage = build_storage_adapter(settings)
    workspace_id = uuid4().hex
    file_id = uuid4().hex
    uri = f"{workspace_id}/files/{file_id}"
    payload = b"blob-storage-roundtrip"

    stored = storage.write(uri, io.BytesIO(payload))
    assert stored.byte_size == len(payload)

    downloaded = b"".join(storage.stream(uri, version_id=stored.version_id))
    assert downloaded == payload

    storage.delete(uri, version_id=stored.version_id)
