"""Tests for CLI runtime helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from backend.api.db.engine import reset_database_state
from backend.api.settings import Settings
from cli.commands import start as start_cmd
from cli.core.runtime import normalise_email, open_session, read_secret


def test_normalise_email_lowercases_and_strips() -> None:
    assert normalise_email("  USER@example.com ") == "user@example.com"


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
            "database_url": f"sqlite+aiosqlite:///{database_path}",
            "data_dir": str(data_dir),
            "documents_dir": str(documents_dir),
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
            "database_url": "sqlite+aiosqlite:///:memory:",
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
        ["ADE_LOG_LEVEL=INFO", "VITE_API_BASE_URL=http://127.0.0.1:8000"]
    )

    assert result == {
        "ADE_LOG_LEVEL": "INFO",
        "VITE_API_BASE_URL": "http://127.0.0.1:8000",
    }


def test_parse_env_pairs_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        start_cmd._parse_env_pairs(["ADE_LOG_LEVEL"])
