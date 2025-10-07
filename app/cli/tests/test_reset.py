"""CLI reset command tests."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from app.cli.commands import reset as reset_command


def _configure_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    database_path = data_dir / "db" / "ade.sqlite"
    documents_dir = data_dir / "documents"

    monkeypatch.setenv("ADE_DATABASE_DSN", f"sqlite+aiosqlite:///{database_path}")
    monkeypatch.setenv("ADE_STORAGE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ADE_STORAGE_DOCUMENTS_DIR", str(documents_dir))

    return database_path, documents_dir


def test_reset_command_removes_sqlite_and_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path, documents_dir = _configure_environment(monkeypatch, tmp_path)

    database_path.parent.mkdir(parents=True)
    database_path.write_text("placeholder", encoding="utf-8")
    (database_path.parent / "ade.sqlite-wal").write_text("", encoding="utf-8")
    (database_path.parent / "ade.sqlite-shm").write_text("", encoding="utf-8")

    documents_dir.mkdir(parents=True)
    (documents_dir / "cached.txt").write_text("cached", encoding="utf-8")
    nested = documents_dir / "nested"
    nested.mkdir()
    (nested / "entry.txt").write_text("nested", encoding="utf-8")

    reset_command.reset(argparse.Namespace(yes=True))

    captured = capsys.readouterr()
    assert "ADE data reset complete." in captured.out

    assert not database_path.exists()
    assert not (database_path.parent / "ade.sqlite-wal").exists()
    assert not (database_path.parent / "ade.sqlite-shm").exists()

    assert documents_dir.exists()
    assert list(documents_dir.iterdir()) == []


def test_reset_command_prompts_and_aborts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path, documents_dir = _configure_environment(monkeypatch, tmp_path)

    database_path.parent.mkdir(parents=True)
    database_path.write_text("placeholder", encoding="utf-8")
    documents_dir.mkdir(parents=True)
    (documents_dir / "cached.txt").write_text("cached", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda _: "n")

    reset_command.reset(argparse.Namespace(yes=False))

    captured = capsys.readouterr()
    assert "Reset aborted." in captured.out

    assert database_path.exists()
    assert documents_dir.exists()
    assert any(documents_dir.iterdir())


def test_reset_command_skips_non_sqlite_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    documents_dir = data_dir / "documents"

    monkeypatch.setenv(
        "ADE_DATABASE_DSN",
        "postgresql+asyncpg://example:secret@example.test:5432/ade",
    )
    monkeypatch.setenv("ADE_STORAGE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ADE_STORAGE_DOCUMENTS_DIR", str(documents_dir))

    documents_dir.mkdir(parents=True)
    (documents_dir / "cached.txt").write_text("cached", encoding="utf-8")

    reset_calls: list[str] = []

    def fake_reset_database_state() -> None:
        reset_calls.append("called")

    monkeypatch.setattr(
        reset_command,
        "reset_database_state",
        fake_reset_database_state,
    )

    def fail_remove(_: Path) -> None:
        raise AssertionError("non-SQLite database should be skipped")

    monkeypatch.setattr(reset_command, "_remove_sqlite_database", fail_remove)

    reset_command.reset(argparse.Namespace(yes=True))

    captured = capsys.readouterr()
    assert "Configured backend 'postgresql' is not SQLite" in captured.out
    assert "ADE data reset complete." in captured.out

    assert reset_calls == ["called"]
    assert documents_dir.exists()
    assert list(documents_dir.iterdir()) == []
