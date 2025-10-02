"""Tests for CLI runtime helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from app.cli.commands import settings as settings_command, start as start_cmd
from app.cli.core.runtime import normalise_email, open_session, read_secret
from app.core.db.engine import reset_database_state
from app.core.config import Settings, reload_settings


def test_normalise_email_lowercases_and_strips() -> None:
    assert normalise_email("  USER@example.test ") == "user@example.test"


@pytest.mark.parametrize("value", ["", "   "])
def test_normalise_email_rejects_blank(value: str) -> None:
    with pytest.raises(ValueError):
        normalise_email(value)


def test_read_secret_returns_first_line(tmp_path: Path) -> None:
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("hunter2\nignored", encoding="utf-8")
    assert read_secret(secret_file) == "hunter2"


def test_read_secret_errors_on_empty_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "empty.txt"
    secret_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        read_secret(secret_file)


@pytest.mark.asyncio()
async def test_open_session_bootstraps_database(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "db" / "cli.sqlite"
    data_dir = tmp_path / "data"
    documents_dir = tmp_path / "documents"

    settings = Settings.model_validate(
        {
            "database_dsn": f"sqlite+aiosqlite:///{database_path}",
            "storage_data_dir": str(data_dir),
            "storage_documents_dir": str(documents_dir),
        }
    )

    reset_database_state()
    try:
        async with open_session(settings=settings) as session:
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
            )
            assert result.scalar_one() == "users"
    finally:
        reset_database_state()


@pytest.mark.asyncio()
async def test_open_session_bootstraps_in_memory_database() -> None:
    settings = Settings.model_validate(
        {
            "database_dsn": "sqlite+aiosqlite:///:memory:",
        }
    )

    reset_database_state()
    try:
        async with open_session(settings=settings) as session:
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
            )
            assert result.scalar_one() == "users"
    finally:
        reset_database_state()


def test_parse_env_pairs_accepts_multiple_values() -> None:
    result = start_cmd._parse_env_pairs(
        ["ADE_LOGGING_LEVEL=INFO", "ADE_DEV_MODE=true"]
    )

    assert result == {
        "ADE_LOGGING_LEVEL": "INFO",
        "ADE_DEV_MODE": "true",
    }


def test_parse_env_pairs_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        start_cmd._parse_env_pairs(["ADE_LOGGING_LEVEL"])


def test_settings_dump_masks_secrets(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ADE_JWT_SECRET", "super-secret")
    reload_settings()

    settings_command.dump(argparse.Namespace())

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["jwt_secret"] == "********"
    reload_settings()
