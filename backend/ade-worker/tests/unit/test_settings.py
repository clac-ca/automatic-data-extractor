from __future__ import annotations

import pytest
from pydantic import ValidationError

from ade_worker.settings import Settings


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
