from __future__ import annotations

import io
import os
import socket
from uuid import uuid4

import pytest

from ade_api.infra.storage import build_storage_adapter
from ade_api.settings import (
    DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP,
    DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES,
    DEFAULT_BLOB_MAX_CONCURRENCY,
    DEFAULT_BLOB_PREFIX,
    DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_BLOB_REQUIRE_VERSIONING,
    DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES,
    Settings,
)


def _env(name: str) -> str | None:
    return os.getenv(name) or os.getenv(f"ADE_{name}")


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _can_connect(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _azurite_env() -> dict[str, object] | None:
    connection_string = (
        os.getenv("AZURITE_CONNECTION_STRING")
        or os.getenv("AZURITE_BLOB_CONNECTION_STRING")
        or _env("BLOB_CONNECTION_STRING")
    )
    container = (
        os.getenv("AZURITE_BLOB_CONTAINER")
        or os.getenv("AZURITE_CONTAINER")
        or _env("BLOB_CONTAINER")
        or "ade-test"
    )
    if connection_string:
        return {
            "container": container,
            "account_url": "",
            "connection_string": connection_string,
            "require_versioning": False,
            "create_container_on_startup": True,
        }

    host_candidates = []
    explicit_host = (_env("AZURITE_BLOB_HOST") or "").strip()
    if explicit_host:
        host_candidates.append(explicit_host)
    host_candidates.extend(["azurite", "localhost"])

    try:
        port = int(_env("AZURITE_BLOB_PORT") or 10000)
    except ValueError:
        port = 10000

    host = next((h for h in host_candidates if _can_connect(h, port)), None)
    if not host:
        return None

    account_name = (
        os.getenv("AZURITE_ACCOUNT_NAME")
        or os.getenv("AZURITE_BLOB_ACCOUNT_NAME")
        or "devstoreaccount1"
    )
    account_key = (
        os.getenv("AZURITE_ACCOUNT_KEY")
        or os.getenv("AZURITE_BLOB_ACCOUNT_KEY")
        or ""
    )
    if not account_key:
        return None

    connection_string = (
        "DefaultEndpointsProtocol=http;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"BlobEndpoint=http://{host}:{port}/{account_name};"
    )

    return {
        "container": container,
        "account_url": "",
        "connection_string": connection_string,
        "require_versioning": False,
        "create_container_on_startup": True,
    }


def _blob_env_ready() -> dict[str, object] | None:
    backend = (_env("STORAGE_BACKEND") or "").strip().lower()
    if backend != "azure_blob":
        return _azurite_env()
    container = _env("BLOB_CONTAINER") or ""
    account_url = _env("BLOB_ACCOUNT_URL") or ""
    connection_string = _env("BLOB_CONNECTION_STRING") or ""

    if not container:
        return None
    if connection_string and account_url:
        return None
    if not connection_string and not account_url:
        return None

    return {
        "container": container,
        "account_url": account_url,
        "connection_string": connection_string,
    }


def test_blob_storage_roundtrip() -> None:
    env = _blob_env_ready()
    if env is None:
        pytest.skip(
            "Azure blob backend not configured; set ADE_STORAGE_BACKEND=azure_blob, "
            "ADE_BLOB_CONTAINER, and ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL."
        )

    require_versioning_default = env.get("require_versioning", DEFAULT_BLOB_REQUIRE_VERSIONING)
    create_container_default = env.get(
        "create_container_on_startup", DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP
    )

    settings = Settings(
        _env_file=None,
        storage_backend="azure_blob",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_account_url=str(env["account_url"]) or None,
        blob_connection_string=str(env["connection_string"]) or None,
        blob_container=str(env["container"]),
        blob_prefix=_env("BLOB_PREFIX") or DEFAULT_BLOB_PREFIX,
        blob_require_versioning=_env_bool(
            "BLOB_REQUIRE_VERSIONING",
            bool(require_versioning_default),
        ),
        blob_create_container_on_startup=_env_bool(
            "BLOB_CREATE_CONTAINER_ON_STARTUP",
            bool(create_container_default),
        ),
        blob_request_timeout_seconds=_env_float(
            "BLOB_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS,
        ),
        blob_max_concurrency=_env_int(
            "BLOB_MAX_CONCURRENCY",
            DEFAULT_BLOB_MAX_CONCURRENCY,
        ),
        blob_upload_chunk_size_bytes=_env_int(
            "BLOB_UPLOAD_CHUNK_SIZE_BYTES",
            DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES,
        ),
        blob_download_chunk_size_bytes=_env_int(
            "BLOB_DOWNLOAD_CHUNK_SIZE_BYTES",
            DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES,
        ),
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
