from __future__ import annotations

import io
from uuid import uuid4

from ade_api.settings import Settings
from ade_storage import build_storage_adapter
from tests.integration_support import test_env as read_test_env


def _build_blob_test_settings() -> Settings:
    blob_container = read_test_env("BLOB_CONTAINER") or "ade-test"
    blob_connection_string = read_test_env("BLOB_CONNECTION_STRING")
    blob_account_url = read_test_env("BLOB_ACCOUNT_URL")
    if not blob_connection_string and not blob_account_url:
        blob_connection_string = "UseDevelopmentStorage=true"

    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container=blob_container,
        blob_connection_string=blob_connection_string,
        blob_account_url=blob_account_url,
        blob_versioning_mode="off",
        secret_key="test-secret-key-for-tests-please-change",
    )


def _ensure_blob_container(settings: Settings) -> None:
    if not settings.blob_connection_string:
        return
    try:
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import BlobServiceClient
    except ModuleNotFoundError:
        return

    service = BlobServiceClient.from_connection_string(settings.blob_connection_string)
    container = service.get_container_client(settings.blob_container)
    try:
        container.create_container()
    except ResourceExistsError:
        pass


def test_blob_storage_roundtrip() -> None:
    settings = _build_blob_test_settings()
    _ensure_blob_container(settings)

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
