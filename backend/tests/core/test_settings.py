from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.api import Settings, get_settings, reload_settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure settings cache and env overrides are cleared between tests."""

    for var in (
        "ADE_APP_NAME",
        "ADE_API_DOCS_ENABLED",
        "ADE_SERVER_HOST",
        "ADE_BACKEND_PORT",
        "ADE_FRONTEND_PORT",
        "ADE_DATA_DIR",
        "ADE_DOCUMENTS_DIR",
        "ADE_DATABASE_URL",
        "ADE_DATABASE_ECHO",
        "ADE_DATABASE_POOL_SIZE",
        "ADE_DATABASE_MAX_OVERFLOW",
        "ADE_DATABASE_POOL_TIMEOUT",
        "ADE_CORS_ALLOW_ORIGINS",
    ):
        monkeypatch.delenv(var, raising=False)
    reload_settings()
    yield
    reload_settings()


def test_settings_defaults() -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.api_docs_enabled is False
    assert settings.server_host == "localhost"
    assert settings.backend_port == 8000
    assert settings.frontend_port == 5173
    assert settings.cors_allow_origins_list == [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    assert settings.database_url.endswith("data/db/ade.sqlite")


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values stored in a local .env file should be honoured."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        """
ADE_APP_NAME=ADE Test
ADE_API_DOCS_ENABLED=true
ADE_SERVER_HOST=dev.local
ADE_BACKEND_PORT=9000
ADE_FRONTEND_PORT=4300
ADE_CORS_ALLOW_ORIGINS=http://localhost:3000,http://example.dev:4000
"""
    )

    monkeypatch.chdir(tmp_path)
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.api_docs_enabled is True
    assert settings.server_host == "dev.local"
    assert settings.backend_port == 9000
    assert settings.frontend_port == 4300
    assert set(settings.cors_allow_origins_list) == {
        "http://dev.local:9000",
        "http://dev.local:4300",
        "http://localhost:3000",
        "http://example.dev:4000",
    }


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should have the final say."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "true")
    monkeypatch.setenv("ADE_SERVER_HOST", "api.local")
    monkeypatch.setenv("ADE_BACKEND_PORT", "8100")
    monkeypatch.setenv("ADE_FRONTEND_PORT", "4300")
    monkeypatch.setenv("ADE_CORS_ALLOW_ORIGINS", "http://example.com")
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.api_docs_enabled is True
    assert settings.server_host == "api.local"
    assert settings.backend_port == 8100
    assert settings.frontend_port == 4300
    assert set(settings.cors_allow_origins_list) == {
        "http://api.local:8100",
        "http://api.local:4300",
        "http://example.com",
    }


def test_docs_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can explicitly disable docs even if previously enabled."""

    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "true")
    reload_settings()
    assert get_settings().api_docs_enabled is True

    monkeypatch.setenv("ADE_API_DOCS_ENABLED", "false")
    reload_settings()
    assert get_settings().api_docs_enabled is False


def test_json_cors_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON encoded origin lists should still be accepted."""

    monkeypatch.setenv("ADE_CORS_ALLOW_ORIGINS", '["http://one.test","http://two.test"]')
    reload_settings()

    settings = get_settings()

    assert set(settings.cors_allow_origins_list) == {
        "http://localhost:5173",
        "http://localhost:8000",
        "http://one.test",
        "http://two.test",
    }
