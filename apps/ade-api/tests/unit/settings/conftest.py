from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from ade_api.settings import reload_settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure settings cache and env overrides are cleared between tests."""

    for var in (
        "ADE_APP_NAME",
        "ADE_API_DOCS_ENABLED",
        "ADE_SAFE_MODE",
        "ADE_LOGGING_LEVEL",
        "ADE_SERVER_PUBLIC_URL",
        "ADE_SERVER_CORS_ORIGINS",
        "ADE_WORKSPACES_DIR",
        "ADE_DOCUMENTS_DIR",
        "ADE_CONFIGS_DIR",
        "ADE_VENVS_DIR",
        "ADE_RUNS_DIR",
        "ADE_PIP_CACHE_DIR",
        "ADE_STORAGE_UPLOAD_MAX_BYTES",
        "ADE_STORAGE_DOCUMENT_RETENTION_PERIOD",
        "ADE_DATABASE_URL",
        "ADE_DATABASE_DSN",
        "ADE_JWT_ACCESS_TTL",
        "ADE_SESSION_COOKIE_NAME",
        "ADE_SESSION_CSRF_COOKIE_NAME",
        "ADE_SESSION_COOKIE_PATH",
        "ADE_SESSION_COOKIE_DOMAIN",
        "ADE_FAILED_LOGIN_LOCK_THRESHOLD",
        "ADE_FAILED_LOGIN_LOCK_DURATION",
        "ADE_MAX_CONCURRENCY",
        "ADE_QUEUE_SIZE",
        "ADE_RUN_LEASE_SECONDS",
        "ADE_RUN_MAX_ATTEMPTS",
        "ADE_RUN_TIMEOUT_SECONDS",
        "ADE_WORKER_CPU_SECONDS",
        "ADE_WORKER_MEM_MB",
        "ADE_WORKER_FSIZE_MB",
        "ADE_OIDC_ENABLED",
        "ADE_OIDC_CLIENT_ID",
        "ADE_OIDC_CLIENT_SECRET",
        "ADE_OIDC_ISSUER",
        "ADE_OIDC_REDIRECT_URL",
        "ADE_OIDC_SCOPES",
        "ADE_AUTH_FORCE_SSO",
        "ADE_AUTH_SSO_AUTO_PROVISION",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ADE_JWT_SECRET", "test-jwt-secret-for-tests-please-change")
    try:
        reload_settings()
    except ValidationError:
        pass
    yield
    try:
        monkeypatch.undo()
        reload_settings()
    except ValidationError:
        pass
