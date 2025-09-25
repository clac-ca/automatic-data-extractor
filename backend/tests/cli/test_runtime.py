"""Tests for CLI runtime helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.cli.core.runtime import normalise_email, read_secret


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
