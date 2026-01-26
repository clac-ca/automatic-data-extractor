from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure settings-related env vars are cleared between tests."""

    for var in (
        "ADE_APP_NAME",
        "ADE_API_DOCS_ENABLED",
        "ADE_SAFE_MODE",
        "ADE_LOG_LEVEL",
        "ADE_SERVER_PUBLIC_URL",
        "ADE_SERVER_CORS_ORIGINS",
        "ADE_DATA_DIR",
        "ADE_ENGINE_PACKAGE_PATH",
        "ADE_STORAGE_BACKEND",
        "ADE_BLOB_ACCOUNT_URL",
        "ADE_BLOB_CONNECTION_STRING",
        "ADE_BLOB_CONTAINER",
        "ADE_BLOB_PREFIX",
        "ADE_BLOB_REQUIRE_VERSIONING",
        "ADE_BLOB_CREATE_CONTAINER_ON_STARTUP",
        "ADE_BLOB_REQUEST_TIMEOUT_SECONDS",
        "ADE_BLOB_MAX_CONCURRENCY",
        "ADE_BLOB_UPLOAD_CHUNK_SIZE_BYTES",
        "ADE_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES",
        "ADE_STORAGE_UPLOAD_MAX_BYTES",
        "ADE_STORAGE_DOCUMENT_RETENTION_PERIOD",
        "ADE_DATABASE_URL",
        "ADE_DATABASE_AUTH_MODE",
        "ADE_DATABASE_SSLROOTCERT",
        "ADE_JWT_ACCESS_TTL",
        "ADE_SESSION_COOKIE_NAME",
        "ADE_SESSION_CSRF_COOKIE_NAME",
        "ADE_SESSION_COOKIE_PATH",
        "ADE_SESSION_COOKIE_DOMAIN",
        "ADE_FAILED_LOGIN_LOCK_THRESHOLD",
        "ADE_FAILED_LOGIN_LOCK_DURATION",
        "ADE_WORKER_CONCURRENCY",
        "ADE_WORKER_POLL_INTERVAL",
        "ADE_WORKER_POLL_INTERVAL_MAX",
        "ADE_WORKER_CLEANUP_INTERVAL",
        "ADE_WORKER_LEASE_SECONDS",
        "ADE_WORKER_MAX_ATTEMPTS_DEFAULT",
        "ADE_WORKER_BACKOFF_BASE_SECONDS",
        "ADE_WORKER_BACKOFF_MAX_SECONDS",
        "ADE_WORKER_LOG_LEVEL",
        "ADE_WORKER_RUN_TIMEOUT_SECONDS",
        "ADE_WORKER_ENV_BUILD_TIMEOUT_SECONDS",
        "ADE_WORKER_ENABLE_GC",
        "ADE_WORKER_GC_INTERVAL_SECONDS",
        "ADE_WORKER_ENV_TTL_DAYS",
        "ADE_WORKER_RUN_ARTIFACT_TTL_DAYS",
        "ADE_WORKER_CPU_SECONDS",
        "ADE_WORKER_MEM_MB",
        "ADE_WORKER_FSIZE_MB",
        "ADE_AUTH_FORCE_SSO",
        "ADE_AUTH_SSO_AUTO_PROVISION",
        "ADE_SSO_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
