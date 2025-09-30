"""Reset command for ADE CLI."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sqlalchemy.engine import URL, make_url

from app.cli.core.runtime import load_settings
from app.core.db.engine import is_sqlite_memory_url, reset_database_state

__all__ = ["register_arguments", "reset"]


def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach options for the ``ade reset`` command."""

    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Reset without prompting for confirmation.",
    )


def reset(args: argparse.Namespace) -> None:
    """Erase the SQLite database and cached documents."""

    settings = load_settings()
    database_path, database_warning = _resolve_database_path(settings.database_dsn)
    documents_path = _absolute_path(settings.storage_documents_dir)

    _print_reset_plan(database_path, database_warning, documents_path)

    if not getattr(args, "yes", False) and not _confirm_reset():
        print("Reset aborted.")
        return

    reset_database_state()

    if database_path is not None:
        _remove_sqlite_database(database_path)

    _reset_directory(documents_path)

    print("ADE data reset complete.")


def _resolve_database_path(database_dsn: str) -> tuple[Path | None, str | None]:
    """Return the filesystem path for a SQLite database if applicable."""

    url = make_url(database_dsn)
    if url.get_backend_name() != "sqlite":
        return None, f"Configured backend '{url.get_backend_name()}' is not SQLite."

    if _is_memory_sqlite(url):
        return None, "SQLite database is in-memory; nothing to delete."

    database = (url.database or "").strip()
    if not database:
        return None, "SQLite database path is empty; nothing to delete."

    return _absolute_path(database), None


def _is_memory_sqlite(url: URL) -> bool:
    """Return ``True`` if ``url`` points at an in-memory SQLite database."""

    return is_sqlite_memory_url(url)


def _remove_sqlite_database(path: Path) -> None:
    """Delete a SQLite database and associated sidecar files."""

    for candidate in _sqlite_sidecar_paths(path):
        _remove_path(candidate)


def _reset_directory(path: Path) -> None:
    """Remove ``path`` and recreate an empty directory."""

    if path.exists():
        _remove_path(path)
    path.mkdir(parents=True, exist_ok=True)


def _print_reset_plan(
    database_path: Path | None, database_warning: str | None, documents_path: Path
) -> None:
    """Describe the artefacts that will be removed."""

    print("This will delete ADE runtime state for the active environment:")
    if database_path is not None:
        print(f"  - SQLite database: {database_path}")
    else:
        reason = database_warning or "No file-based database configured."
        print(f"  - SQLite database: skipped ({reason})")
    print(f"  - cached documents directory: {documents_path}")
    print("This action cannot be undone.")


def _confirm_reset() -> bool:
    """Prompt the operator for confirmation."""

    response = input("Proceed with deletion? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _absolute_path(path: Path | str) -> Path:
    """Return an absolute version of ``path`` relative to the working directory."""

    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path.cwd() / candidate


def _sqlite_sidecar_paths(path: Path) -> list[Path]:
    """Return sidecar artefacts produced by SQLite journaling modes."""

    return [
        path,
        path.with_name(path.name + "-wal"),
        path.with_name(path.name + "-shm"),
        path.with_name(path.name + "-journal"),
    ]


def _remove_path(path: Path) -> None:
    """Best-effort removal for a file or directory."""

    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except FileNotFoundError:
        return
