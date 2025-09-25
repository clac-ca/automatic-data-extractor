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
        "ADE_ENVIRONMENT",
        "ADE_DATA_DIR",
        "ADE_DOCUMENTS_DIR",
        "ADE_DATABASE_URL",
        "ADE_DATABASE_ECHO",
        "ADE_DATABASE_POOL_SIZE",
        "ADE_DATABASE_MAX_OVERFLOW",
        "ADE_DATABASE_POOL_TIMEOUT",
    ):
        monkeypatch.delenv(var, raising=False)
    reload_settings()
    yield
    reload_settings()


def test_settings_defaults() -> None:
    """Default settings should expose the ADE metadata."""

    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.environment == "local"
    assert settings.database_url.endswith("data/db/ade.sqlite")
    assert settings.database_echo is False
    assert settings.docs_enabled is True
    docs_url, redoc_url = settings.docs_urls
    assert docs_url == "/docs"
    assert redoc_url == "/redoc"
    assert settings.openapi_docs_url == "/openapi.json"


def test_settings_reads_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should honour values stored in a local .env file."""

    env_file = tmp_path / ".env"
    env_file.write_text("""\nADE_APP_NAME=ADE Test\nADE_ENABLE_DOCS=false\n""")

    monkeypatch.chdir(tmp_path)
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.docs_enabled is False


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override default values."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_ENABLE_DOCS", "false")
    reload_settings()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.docs_enabled is False


def test_docs_disabled_by_default_outside_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docs should be hidden when the environment is not allow-listed."""

    monkeypatch.setenv("ADE_ENVIRONMENT", "production")
    reload_settings()

    settings = get_settings()

    assert settings.docs_enabled is False
    docs_url, redoc_url = settings.docs_urls
    assert docs_url is None
    assert redoc_url is None
    assert settings.openapi_docs_url is None


def test_docs_override_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit enable override should surface docs even in production."""

    monkeypatch.setenv("ADE_ENVIRONMENT", "production")
    monkeypatch.setenv("ADE_ENABLE_DOCS", "true")
    reload_settings()

    settings = get_settings()

    assert settings.docs_enabled is True
    assert settings.docs_urls == ("/docs", "/redoc")
    assert settings.openapi_docs_url == "/openapi.json"


def test_docs_override_can_disable_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can still disable docs explicitly for local environments."""

    monkeypatch.setenv("ADE_ENABLE_DOCS", "false")
    reload_settings()

    settings = get_settings()

    assert settings.docs_enabled is False
    assert settings.docs_urls == (None, None)
    assert settings.openapi_docs_url is None
