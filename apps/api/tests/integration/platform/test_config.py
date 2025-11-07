"""Settings configuration tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.app.settings import Settings, get_settings, reload_settings
from apps.api.app.shared.core.lifecycles import ensure_runtime_dirs


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure settings cache and env overrides are cleared between tests."""

    for var in (
        "ADE_APP_NAME",
        "ADE_API_DOCS_ENABLED",
        "ADE_DEBUG",
        "ADE_DEV_MODE",
        "ADE_SAFE_MODE",
        "ADE_LOGGING_LEVEL",
        "ADE_SERVER_HOST",
        "ADE_SERVER_PORT",
        "ADE_SERVER_PUBLIC_URL",
        "ADE_SERVER_CORS_ORIGINS",
        "ADE_DATA_DIR",
        "ADE_DOCUMENTS_DIR",
        "ADE_CONFIGS_DIR",
        "ADE_VENVS_DIR",
        "ADE_JOBS_DIR",
        "ADE_PIP_CACHE_DIR",
        "ADE_STORAGE_UPLOAD_MAX_BYTES",
        "ADE_STORAGE_DOCUMENT_RETENTION_PERIOD",
        "ADE_SECRET_KEY",
        "ADE_DATABASE_DSN",
        "ADE_JWT_SECRET",
        "ADE_JWT_ACCESS_TTL",
        "ADE_JWT_REFRESH_TTL",
        "ADE_SESSION_LAST_SEEN_INTERVAL",
        "ADE_SESSION_COOKIE_NAME",
        "ADE_SESSION_REFRESH_COOKIE_NAME",
        "ADE_SESSION_CSRF_COOKIE_NAME",
        "ADE_SESSION_COOKIE_PATH",
        "ADE_SESSION_COOKIE_DOMAIN",
        "ADE_FAILED_LOGIN_LOCK_THRESHOLD",
        "ADE_FAILED_LOGIN_LOCK_DURATION",
        "ADE_MAX_CONCURRENCY",
        "ADE_QUEUE_SIZE",
        "ADE_JOB_TIMEOUT_SECONDS",
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
    try:
        reload_settings()
    except ValidationError:
        pass
    yield
    try:
        reload_settings()
    except ValidationError:
        pass


def test_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    monkeypatch.chdir(tmp_path)
    reload_settings()
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.api_docs_enabled is False
    assert settings.server_host == "localhost"
    assert settings.server_port == 8000
    assert settings.server_public_url == "http://localhost:8000"
    assert settings.server_cors_origins == ["http://localhost:5173"]
    assert settings.database_dsn.endswith("data/db/ade.sqlite")
    assert settings.jwt_access_ttl == timedelta(minutes=60)
    assert settings.jwt_refresh_ttl == timedelta(days=14)
    assert settings.documents_dir == settings.data_dir / "documents"
    assert settings.configs_dir == settings.data_dir / "config_packages"
    assert settings.venvs_dir == settings.data_dir / "venvs"
    assert settings.jobs_dir == settings.data_dir / "jobs"
    assert settings.pip_cache_dir == settings.data_dir / "cache" / "pip"


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values stored in a local .env file should be honoured."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        """
ADE_APP_NAME=ADE Test
ADE_API_DOCS_ENABLED=true
ADE_SERVER_HOST=0.0.0.0
ADE_SERVER_PORT=9000
ADE_SERVER_PUBLIC_URL=https://api.dev.local
ADE_SERVER_CORS_ORIGINS=http://localhost:3000,http://example.dev:4000
ADE_JWT_ACCESS_TTL=5m
ADE_JWT_REFRESH_TTL=7d
"""
    )

    monkeypatch.chdir(tmp_path)
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.api_docs_enabled is True
    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9000
    assert settings.server_public_url == "https://api.dev.local"
    assert settings.server_cors_origins == [
        "http://localhost:3000",
        "http://example.dev:4000",
    ]
    assert settings.jwt_access_ttl == timedelta(minutes=5)
    assert settings.jwt_refresh_ttl == timedelta(days=7)


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should have the final say."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "true")
    monkeypatch.setenv("ADE_SERVER_HOST", "dev.internal")
    monkeypatch.setenv("ADE_SERVER_PORT", "8100")
    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://api.local")
    monkeypatch.setenv("ADE_SERVER_CORS_ORIGINS", "http://example.com")
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.api_docs_enabled is True
    assert settings.server_host == "dev.internal"
    assert settings.server_port == 8100
    assert settings.server_public_url == "https://api.local"
    assert settings.server_cors_origins == ["http://example.com"]


def test_cors_accepts_comma_separated_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma separated origin lists should be accepted."""

    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        "http://one.test,http://two.test",
    )
    reload_settings()

    settings = get_settings()

    assert settings.server_cors_origins == ["http://one.test", "http://two.test"]


def test_cors_deduplicates_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma separated CORS entries should be normalised and deduplicated."""

    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        "http://one.test,http://two.test,http://one.test",
    )
    reload_settings()

    settings = get_settings()

    assert settings.server_cors_origins == ["http://one.test", "http://two.test"]


def test_server_public_url_accepts_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPS URLs should be accepted for the public origin."""

    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://secure.example.com")
    reload_settings()

    settings = get_settings()

    assert settings.server_public_url == "https://secure.example.com"
    assert settings.server_cors_origins == ["http://localhost:5173"]


def test_storage_directories_follow_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Documents directory should default inside the configured data directory."""

    data_dir = tmp_path / "api-app-data"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    reload_settings()

    settings = get_settings()

    assert settings.data_dir == data_dir.resolve()
    assert settings.documents_dir == (data_dir / "documents").resolve()
    assert settings.configs_dir == (data_dir / "config_packages").resolve()
    assert settings.venvs_dir == (data_dir / "venvs").resolve()
    assert settings.jobs_dir == (data_dir / "jobs").resolve()
    assert settings.pip_cache_dir == (data_dir / "cache" / "pip").resolve()


def test_global_storage_directory_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_runtime_dirs should create the storage directory and return it."""

    data_dir = tmp_path / "api-app-data"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    reload_settings()

    ensure_runtime_dirs()

    assert data_dir.exists()
    assert (data_dir / "documents").exists()
    assert (data_dir / "config_packages").exists()
    assert (data_dir / "venvs").exists()
    assert (data_dir / "jobs").exists()
    assert (data_dir / "cache" / "pip").exists()


def test_storage_directory_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ADE_*_DIR overrides should be honoured."""

    data_dir = tmp_path / "api-app-data"
    configs_dir = tmp_path / "alt-configs"
    venvs_dir = tmp_path / "alt-venvs"
    jobs_dir = tmp_path / "alt-jobs"
    pip_cache_dir = tmp_path / "alt-cache" / "pip"

    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ADE_CONFIGS_DIR", str(configs_dir))
    monkeypatch.setenv("ADE_VENVS_DIR", str(venvs_dir))
    monkeypatch.setenv("ADE_JOBS_DIR", str(jobs_dir))
    monkeypatch.setenv("ADE_PIP_CACHE_DIR", str(pip_cache_dir))
    reload_settings()

    settings = get_settings()

    assert settings.configs_dir == configs_dir.resolve()
    assert settings.venvs_dir == venvs_dir.resolve()
    assert settings.jobs_dir == jobs_dir.resolve()
    assert settings.pip_cache_dir == pip_cache_dir.resolve()
