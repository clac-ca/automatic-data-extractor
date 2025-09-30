from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import Settings, get_settings, reload_settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure settings cache and env overrides are cleared between tests."""

    for var in (
        "ADE_APP_NAME",
        "ADE_API_DOCS_ENABLED",
        "ADE_SERVER_HOST",
        "ADE_SERVER_PORT",
        "ADE_SERVER_PUBLIC_URL",
        "ADE_SERVER_CORS_ORIGINS",
        "ADE_STORAGE_DATA_DIR",
        "ADE_STORAGE_DOCUMENTS_DIR",
        "ADE_STORAGE_DOCUMENT_RETENTION_PERIOD",
        "ADE_STORAGE_UPLOAD_MAX_BYTES",
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
        "ADE_OIDC_ENABLED",
        "ADE_OIDC_CLIENT_ID",
        "ADE_OIDC_CLIENT_SECRET",
        "ADE_OIDC_ISSUER",
        "ADE_OIDC_REDIRECT_URL",
        "ADE_OIDC_SCOPES",
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


def test_settings_defaults() -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.api_docs_enabled is False
    assert settings.server_host == "localhost"
    assert settings.server_port == 8000
    assert str(settings.server_public_url) == "http://localhost:8000/"
    assert [str(origin) for origin in settings.server_cors_origins] == [
        "http://localhost:8000/"
    ]
    assert settings.database_dsn.endswith("var/db/ade.sqlite")
    assert settings.jwt_access_ttl == timedelta(minutes=60)
    assert settings.jwt_refresh_ttl == timedelta(days=14)
    assert settings.storage_documents_dir == settings.storage_data_dir / "documents"


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
    assert str(settings.server_public_url) == "https://api.dev.local/"
    assert set(str(origin) for origin in settings.server_cors_origins) == {
        "https://api.dev.local/",
        "http://localhost:3000/",
        "http://example.dev:4000/",
    }
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
    assert str(settings.server_public_url) == "https://api.local/"
    assert set(str(origin) for origin in settings.server_cors_origins) == {
        "https://api.local/",
        "http://example.com/",
    }


def test_json_cors_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON encoded origin lists should still be accepted."""

    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        '["http://one.test","http://two.test"]',
    )
    reload_settings()

    settings = get_settings()

    assert set(str(origin) for origin in settings.server_cors_origins) == {
        "http://localhost:8000/",
        "http://one.test/",
        "http://two.test/",
    }


def test_cors_accepts_whitespace_delimiters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma, space, or newline separated CORS origins should all parse."""

    monkeypatch.setenv(
        "ADE_SERVER_CORS_ORIGINS",
        "http://one.test\nhttp://two.test   http://three.test",
    )
    reload_settings()

    settings = get_settings()

    assert set(str(origin) for origin in settings.server_cors_origins) == {
        "http://localhost:8000/",
        "http://one.test/",
        "http://two.test/",
        "http://three.test/",
    }


def test_server_public_url_accepts_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPS URLs should be accepted for the public origin."""

    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://secure.example.com")
    reload_settings()

    settings = get_settings()

    assert str(settings.server_public_url) == "https://secure.example.com/"
    assert [str(origin) for origin in settings.server_cors_origins] == [
        "https://secure.example.com/"
    ]


def test_storage_directories_follow_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Documents directory should default inside the configured data directory."""

    data_dir = tmp_path / "ade-data"
    monkeypatch.setenv("ADE_STORAGE_DATA_DIR", str(data_dir))
    reload_settings()

    settings = get_settings()

    assert settings.storage_data_dir == data_dir.resolve()
    assert settings.storage_documents_dir == data_dir.resolve() / "documents"
    assert settings.storage_documents_dir.is_dir()


def test_oidc_requires_complete_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Partial OIDC configuration should raise a validation error."""

    monkeypatch.setenv("ADE_OIDC_ENABLED", "true")
    monkeypatch.setenv("ADE_OIDC_CLIENT_ID", "example-client")
    monkeypatch.setenv("ADE_OIDC_ISSUER", "https://issuer.example.com")
    with pytest.raises(ValidationError):
        reload_settings()


def test_oidc_complete_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing all OIDC values should enable the feature and parse scopes."""

    monkeypatch.setenv("ADE_OIDC_ENABLED", "true")
    monkeypatch.setenv("ADE_OIDC_CLIENT_ID", "example-client")
    monkeypatch.setenv("ADE_OIDC_CLIENT_SECRET", "super-secret")
    monkeypatch.setenv("ADE_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_OIDC_REDIRECT_URL", "https://app.example.com/callback")
    monkeypatch.setenv("ADE_OIDC_SCOPES", "openid, email profile,custom")
    reload_settings()

    settings = get_settings()

    assert settings.oidc_enabled is True
    assert settings.oidc_scopes == ["custom", "email", "openid", "profile"]


def test_session_cookie_fields_trim_and_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookie configuration should trim whitespace and require valid values."""

    monkeypatch.setenv("ADE_SESSION_COOKIE_NAME", " ade_cookie ")
    monkeypatch.setenv("ADE_SESSION_REFRESH_COOKIE_NAME", "\tade_refresh")
    monkeypatch.setenv("ADE_SESSION_CSRF_COOKIE_NAME", "ade-csrf")
    monkeypatch.setenv("ADE_SESSION_COOKIE_PATH", " /api ")
    reload_settings()

    settings = get_settings()

    assert settings.session_cookie_name == "ade_cookie"
    assert settings.session_refresh_cookie_name == "ade_refresh"
    assert settings.session_csrf_cookie_name == "ade-csrf"
    assert settings.session_cookie_path == "/api"


def test_session_cookie_name_rejects_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookie names containing spaces should raise a validation error."""

    monkeypatch.setenv("ADE_SESSION_COOKIE_NAME", "bad cookie")

    with pytest.raises(ValidationError):
        reload_settings()


def test_session_cookie_path_requires_leading_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookie paths must start with a forward slash."""

    monkeypatch.setenv("ADE_SESSION_COOKIE_PATH", "cookies")

    with pytest.raises(ValidationError):
        reload_settings()


def test_duration_parsing_supports_suffixes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duration fields should accept suffixed strings and plain seconds."""

    monkeypatch.setenv("ADE_JWT_ACCESS_TTL", "45 minutes")
    monkeypatch.setenv("ADE_JWT_REFRESH_TTL", "1 h")
    monkeypatch.setenv("ADE_SESSION_LAST_SEEN_INTERVAL", "90s")
    monkeypatch.setenv("ADE_STORAGE_DOCUMENT_RETENTION_PERIOD", "2592000")
    reload_settings()

    settings = get_settings()

    assert settings.jwt_access_ttl == timedelta(minutes=45)
    assert settings.jwt_refresh_ttl == timedelta(hours=1)
    assert settings.session_last_seen_interval == timedelta(seconds=90)
    assert settings.storage_document_retention_period == timedelta(days=30)


def test_storage_upload_max_bytes_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upload limit must be greater than zero."""

    monkeypatch.setenv("ADE_STORAGE_UPLOAD_MAX_BYTES", "0")

    with pytest.raises(ValidationError):
        reload_settings()
