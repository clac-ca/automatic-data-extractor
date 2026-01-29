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
        secret_key="test-secret-key-for-tests-please-change",
    )

    from azure.core.exceptions import HttpResponseError
    from azure.storage.blob import BlobServiceClient

    if settings.blob_connection_string:
        service = BlobServiceClient.from_connection_string(
            conn_str=settings.blob_connection_string
        )
    else:
        from azure.identity import DefaultAzureCredential

        if not settings.blob_account_url:
            raise RuntimeError("Blob storage is not configured for tests.")
        service = BlobServiceClient(
            account_url=settings.blob_account_url,
            credential=DefaultAzureCredential(),
        )
    container = service.get_container_client(settings.blob_container or "")
    try:
        container.create_container()
    except HttpResponseError as exc:
        if exc.status_code != 409:
            raise

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
