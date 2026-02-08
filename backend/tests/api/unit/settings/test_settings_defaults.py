from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from ade_api.settings import Settings
from paths import REPO_ROOT

REQUIRED_DATABASE_URL = "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable"


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    settings = Settings(_env_file=None)

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.app_version == "unknown"
    assert settings.app_commit_sha == "unknown"
    assert settings.api_docs_enabled is False
    assert settings.api_processes is None
    assert settings.api_proxy_headers_enabled is True
    assert settings.api_forwarded_allow_ips == "127.0.0.1"
    assert settings.api_threadpool_tokens == 40
    assert settings.public_web_url == "http://localhost:8000"
    assert settings.server_cors_origins == []
    assert settings.server_cors_origin_regex is None
    url = make_url(str(settings.database_url))
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "postgres"
    assert url.port == 5432
    assert url.database == "ade"
    assert url.username == "ade"
    assert url.password == "ade"
    assert url.query.get("sslmode") == "disable"
    assert settings.access_token_expire_minutes == 30
    expected_root = REPO_ROOT / "backend" / "data"
    expected_workspaces = expected_root / "workspaces"
    expected_venvs = expected_root / "venvs"
    assert settings.data_dir == expected_root
    assert settings.workspaces_dir == expected_workspaces
    assert settings.documents_dir == expected_workspaces
    assert settings.configs_dir == expected_workspaces
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_workspaces
    assert settings.pip_cache_dir == expected_root / "cache" / "pip"
    assert settings.blob_account_url is None
    assert settings.blob_container == "ade-test"
    assert settings.blob_prefix == "workspaces"
    assert settings.blob_versioning_mode == "auto"
    assert settings.database_connection_budget is None
    assert settings.auth_password_reset_enabled is True
    assert settings.auth_enforce_local_mfa is False


def test_data_dir_propagates_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADE_DATA_DIR should become the root for workspace-owned storage."""

    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_DATA_DIR", "./custom/data-root")

    settings = Settings(_env_file=None)

    expected_root = REPO_ROOT / "custom" / "data-root"
    expected_workspaces = expected_root / "workspaces"
    expected_venvs = expected_root / "venvs"
    assert settings.data_dir == expected_root
    assert settings.workspaces_dir == expected_workspaces
    assert settings.documents_dir == expected_workspaces
    assert settings.configs_dir == expected_workspaces
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_workspaces


def test_app_version_uses_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_APP_VERSION", "9.9.9")

    settings = Settings(_env_file=None)

    assert settings.app_version == "9.9.9"


def test_app_commit_sha_uses_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_APP_COMMIT_SHA", "abc1234")

    settings = Settings(_env_file=None)

    assert settings.app_commit_sha == "abc1234"
