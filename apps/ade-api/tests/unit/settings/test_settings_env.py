from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from ade_api.settings import get_settings, reload_settings


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values stored in a local .env file should be honoured."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        """
ADE_APP_NAME=ADE Test
ADE_API_DOCS_ENABLED=true
ADE_SERVER_PUBLIC_URL=https://api.dev.local
ADE_SERVER_CORS_ORIGINS=http://localhost:3000,http://example.dev:4000
ADE_JWT_ACCESS_TTL=5m
"""
    )

    monkeypatch.chdir(tmp_path)
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.api_docs_enabled is True
    assert settings.server_public_url == "https://api.dev.local"
    assert settings.server_cors_origins == [
        "http://localhost:3000",
        "http://example.dev:4000",
    ]
    assert settings.jwt_access_ttl == timedelta(minutes=5)


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should have the final say."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "true")
    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://api.local")
    monkeypatch.setenv("ADE_SERVER_CORS_ORIGINS", "http://example.com")
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.api_docs_enabled is True
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
