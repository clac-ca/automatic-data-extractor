from __future__ import annotations

import re
from pathlib import Path

import pytest
from ade_api.settings import Settings
from pydantic import ValidationError


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values stored in a local .env file should be honoured."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        """
ADE_APP_NAME=ADE Test
ADE_API_DOCS_ENABLED=true
ADE_PUBLIC_WEB_URL=https://api.dev.local
ADE_SERVER_CORS_ORIGINS=http://localhost:3000,http://example.dev:4000
ADE_SERVER_CORS_ORIGIN_REGEX=^https://.*\\.dev\\.local$
ADE_SECRET_KEY=test-secret-key-for-tests-please-change
ADE_ACCESS_TOKEN_EXPIRE_MINUTES=5
ADE_DATABASE_URL=postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable
ADE_BLOB_CONTAINER=ade-test
ADE_BLOB_CONNECTION_STRING=UseDevelopmentStorage=true
"""
    )

    settings = Settings(_env_file=str(env_file))

    assert settings.app_name == "ADE Test"
    assert settings.api_docs_enabled is True
    assert settings.public_web_url == "https://api.dev.local"
    assert settings.server_cors_origins == [
        "http://localhost:3000",
        "http://example.dev:4000",
    ]
    assert settings.server_cors_origin_regex == r"^https://.*\.dev\.local$"
    assert settings.access_token_expire_minutes == 5


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should have the final say."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "true")
    monkeypatch.setenv("ADE_PUBLIC_WEB_URL", "https://api.local")
    monkeypatch.setenv("ADE_SERVER_CORS_ORIGINS", "http://example.com")
    monkeypatch.setenv("ADE_SERVER_CORS_ORIGIN_REGEX", "^https://.*\\.example\\.com$")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    settings = Settings(_env_file=None)

    assert settings.app_name == "Env Override"
    assert settings.api_docs_enabled is True
    assert settings.public_web_url == "https://api.local"
    assert settings.server_cors_origins == ["http://example.com"]
    assert settings.server_cors_origin_regex == r"^https://.*\.example\.com$"


def test_api_processes_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_API_PROCESSES", "3")

    settings = Settings(_env_file=None)

    assert settings.api_processes == 3


def test_api_runtime_tuning_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_API_PROXY_HEADERS_ENABLED", "false")
    monkeypatch.setenv("ADE_API_FORWARDED_ALLOW_IPS", "10.0.0.1,10.0.0.2")
    monkeypatch.setenv("ADE_API_THREADPOOL_TOKENS", "64")
    monkeypatch.setenv("ADE_CONFIG_IMPORT_MAX_BYTES", "73400320")
    monkeypatch.setenv("ADE_DATABASE_CONNECTION_BUDGET", "120")
    monkeypatch.setenv("ADE_AUTH_ENFORCE_LOCAL_MFA", "true")

    settings = Settings(_env_file=None)

    assert settings.api_proxy_headers_enabled is False
    assert settings.api_forwarded_allow_ips == "10.0.0.1,10.0.0.2"
    assert settings.api_threadpool_tokens == 64
    assert settings.config_import_max_bytes == 73400320
    assert settings.database_connection_budget == 120
    assert settings.auth_enforce_local_mfa is True


def test_api_forwarded_allow_ips_must_not_be_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_API_FORWARDED_ALLOW_IPS", "   ")

    with pytest.raises(ValidationError, match="ADE_API_FORWARDED_ALLOW_IPS"):
        Settings(_env_file=None)


def test_cors_accepts_comma_separated_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma separated origin lists should be accepted."""

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        "http://one.test,http://two.test",
    )
    settings = Settings(_env_file=None)

    assert settings.server_cors_origins == ["http://one.test", "http://two.test"]


def test_cors_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma separated CORS entries should be parsed in order."""

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        "http://one.test,http://two.test,http://one.test",
    )
    settings = Settings(_env_file=None)

    assert settings.server_cors_origins == [
        "http://one.test",
        "http://two.test",
        "http://one.test",
    ]


def test_public_web_url_accepts_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPS URLs should be accepted for the public origin."""

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_PUBLIC_WEB_URL", "https://secure.example.com")
    settings = Settings(_env_file=None)

    assert settings.public_web_url == "https://secure.example.com"
    assert settings.server_cors_origins == []
    assert settings.server_cors_origin_regex is None


def test_password_reset_toggle_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_RESET_ENABLED", "false")
    monkeypatch.setenv("ADE_AUTH_ENFORCE_LOCAL_MFA", "true")

    settings = Settings(_env_file=None)

    assert settings.auth_password_reset_enabled is False
    assert settings.auth_enforce_local_mfa is True




def test_logging_level_falls_back_to_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADE_LOG_LEVEL should set the API log level."""
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_LOG_LEVEL", "warning")
    settings = Settings(_env_file=None)

    assert settings.log_level == "WARNING"


def test_logging_level_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service-specific logging overrides should take precedence over ADE_LOG_LEVEL."""

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_LOG_LEVEL", "warning")
    monkeypatch.setenv("ADE_API_LOG_LEVEL", "error")
    monkeypatch.setenv("ADE_REQUEST_LOG_LEVEL", "info")
    monkeypatch.setenv("ADE_ACCESS_LOG_LEVEL", "debug")
    monkeypatch.setenv("ADE_LOG_FORMAT", "JSON")
    settings = Settings(_env_file=None)

    assert settings.log_format == "json"
    assert settings.log_level == "WARNING"
    assert settings.effective_api_log_level == "ERROR"
    assert settings.effective_request_log_level == "INFO"
    assert settings.effective_access_log_level == "DEBUG"


@pytest.mark.parametrize(
    ("env_name", "value"),
    [
        ("ADE_LOG_LEVEL", "verbose"),
        ("ADE_API_LOG_LEVEL", "noisy"),
        ("ADE_REQUEST_LOG_LEVEL", "trace"),
        ("ADE_ACCESS_LOG_LEVEL", "chatty"),
        ("ADE_DATABASE_LOG_LEVEL", "sql"),
    ],
)
def test_invalid_log_levels_raise_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    value: str,
) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv(env_name, value)

    with pytest.raises(ValidationError, match=env_name):
        Settings(_env_file=None)


def test_invalid_log_format_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_LOG_FORMAT", "pretty")

    with pytest.raises(ValidationError, match="ADE_LOG_FORMAT"):
        Settings(_env_file=None)


def test_cors_origin_regex_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid CORS origin regex should raise a settings error."""

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_SERVER_CORS_ORIGIN_REGEX", "(")

    with pytest.raises(re.error):
        Settings(_env_file=None)
