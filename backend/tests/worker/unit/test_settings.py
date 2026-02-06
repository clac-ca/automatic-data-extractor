from __future__ import annotations

import pytest
from pydantic import ValidationError

from ade_worker.settings import Settings
from paths import REPO_ROOT


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ADE_DATABASE_URL",
        "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
    )
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")


def test_worker_log_level_inherits_global_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_LOG_LEVEL", "warning")

    settings = Settings(_env_file=None)

    assert settings.log_level == "WARNING"
    assert settings.worker_log_level is None
    assert settings.effective_worker_log_level == "WARNING"


def test_worker_log_level_override_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_LOG_LEVEL", "warning")
    monkeypatch.setenv("ADE_WORKER_LOG_LEVEL", "error")

    settings = Settings(_env_file=None)

    assert settings.log_level == "WARNING"
    assert settings.worker_log_level == "ERROR"
    assert settings.effective_worker_log_level == "ERROR"


def test_worker_log_format_normalizes_case(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_LOG_FORMAT", "JSON")

    settings = Settings(_env_file=None)

    assert settings.log_format == "json"


@pytest.mark.parametrize(
    ("env_name", "value"),
    [
        ("ADE_LOG_LEVEL", "verbose"),
        ("ADE_WORKER_LOG_LEVEL", "chatty"),
    ],
)
def test_invalid_worker_log_level_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    value: str,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv(env_name, value)

    with pytest.raises(ValidationError, match=env_name):
        Settings(_env_file=None)


def test_invalid_worker_log_format_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_LOG_FORMAT", "plain")

    with pytest.raises(ValidationError, match="ADE_LOG_FORMAT"):
        Settings(_env_file=None)


def test_worker_data_dir_default_matches_api_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    expected_root = REPO_ROOT / "backend" / "data"
    assert settings.data_dir == expected_root
    assert settings.workspaces_dir == expected_root / "workspaces"
    assert settings.venvs_dir == expected_root / "venvs"
    assert settings.pip_cache_dir == expected_root / "cache" / "pip"
    assert settings.blob_versioning_mode == "auto"


def test_worker_run_concurrency_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_WORKER_RUN_CONCURRENCY", "7")

    settings = Settings(_env_file=None)

    assert settings.worker_run_concurrency == 7


@pytest.mark.parametrize(
    ("env_name", "value", "expected_mode"),
    [
        ("ADE_BLOB_VERSIONING_MODE", "require", "require"),
        ("ADE_BLOB_VERSIONING_MODE", "off", "off"),
    ],
)
def test_worker_blob_versioning_mode_parsing(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    value: str,
    expected_mode: str,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv(env_name, value)

    settings = Settings(_env_file=None)

    assert settings.blob_versioning_mode == expected_mode
