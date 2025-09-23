"""Tests for the application settings loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core.settings import AppSettings, get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure settings cache and env overrides are cleared between tests."""

    for var in (
        "ADE_SETTINGS_FILES",
        "ADE_SECRETS_FILES",
        "ADE_ENV",
        "ADE_APP_ENV",
        "APP_ENV",
        "ADE_APP_NAME",
        "ADE_ENABLE_DOCS",
        "ADE_DATABASE_URL",
        "ADE_DATABASE_ECHO",
        "ADE_DATABASE_POOL_SIZE",
        "ADE_DATABASE_MAX_OVERFLOW",
        "ADE_DATABASE_POOL_TIMEOUT",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_settings_defaults() -> None:
    """Default settings should expose the ADE metadata."""

    settings = get_settings()
    assert isinstance(settings, AppSettings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.environment == "local"
    assert settings.database_url.endswith("data/db/ade.sqlite")
    assert settings.database_echo is False
    docs_url, redoc_url = settings.docs_urls
    assert docs_url == "/docs"
    assert redoc_url == "/redoc"


def test_settings_reads_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should merge default and environment-specific TOML sections."""

    toml_payload = """
    [default]
    app_name = "ADE Test"
    log_level = "DEBUG"

    [testing]
    enable_docs = false
    debug = true
    docs_url = "/debug-docs"
    redoc_url = "/debug-redoc"
    """
    config_path = tmp_path / "settings.toml"
    config_path.write_text(toml_payload)

    monkeypatch.setenv("ADE_SETTINGS_FILES", str(config_path))
    monkeypatch.setenv("ADE_ENV", "testing")
    reset_settings_cache()

    settings = get_settings()

    assert settings.app_name == "ADE Test"
    assert settings.log_level == "DEBUG"
    assert settings.environment == "testing"
    assert settings.debug is True
    docs_url, redoc_url = settings.docs_urls
    assert docs_url is None
    assert redoc_url is None


def test_settings_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override file and default values."""

    monkeypatch.setenv("ADE_APP_NAME", "Env Override")
    monkeypatch.setenv("ADE_ENABLE_DOCS", "false")
    reset_settings_cache()

    settings = get_settings()

    assert settings.app_name == "Env Override"
    assert settings.enable_docs is False
