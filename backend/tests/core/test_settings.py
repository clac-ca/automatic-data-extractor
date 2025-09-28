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
        "ADE_ENABLE_DOCS",
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
    assert settings.enable_docs is False
    assert settings.docs_enabled is False
    assert settings.cors_allow_origins_list == []
    assert settings.database_url.endswith("data/db/ade.sqlite")


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values stored in a local .env file should be honoured."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        """\nADE_APP_NAME=ADE Test\nADE_ENABLE_DOCS=true\nADE_CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000\n"""
    )

    monkeypatch.chdir(tmp_path)
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.docs_enabled is True
    assert settings.cors_allow_origins_list == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should have the final say."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_ENABLE_DOCS", "true")
    monkeypatch.setenv("ADE_CORS_ALLOW_ORIGINS", "http://example.com")
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.docs_enabled is True
    assert settings.cors_allow_origins_list == ["http://example.com"]


def test_docs_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can explicitly disable docs even if previously enabled."""

    monkeypatch.setenv("ADE_ENABLE_DOCS", "true")
    reload_settings()
    assert get_settings().docs_enabled is True

    monkeypatch.setenv("ADE_ENABLE_DOCS", "false")
    reload_settings()
    assert get_settings().docs_enabled is False


def test_json_cors_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON encoded origin lists should still be accepted."""

    monkeypatch.setenv("ADE_CORS_ALLOW_ORIGINS", '["http://one.test","http://two.test"]')
    reload_settings()

    settings = get_settings()

    assert settings.cors_allow_origins_list == ["http://one.test", "http://two.test"]
