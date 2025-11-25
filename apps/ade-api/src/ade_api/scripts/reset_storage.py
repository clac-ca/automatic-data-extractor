"""CLI to purge ADE storage directories resolved from backend settings."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy.engine import make_url

from ..settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_STORAGE_ROOT = (REPO_ROOT / "data").resolve()


def _normalize(path: Path | str | None) -> Path | None:
    if path in (None, "", "."):
        return None
    candidate = path if isinstance(path, Path) else Path(path)
    resolved = candidate.expanduser().resolve()
    if resolved == resolved.parent:
        return None
    return resolved


def _within_default_root(path: Path) -> bool:
    try:
        path.relative_to(DEFAULT_STORAGE_ROOT)
    except ValueError:
        return False
    return True


def _resolve_sqlite_database_path(settings: Settings) -> Path | None:
    url = make_url(settings.database_dsn)
    if url.get_backend_name() != "sqlite":
        return None

    database = (url.database or "").strip()
    if not database or database == ":memory:" or database.startswith("file:"):
        return None

    db_path = Path(database)
    if not db_path.is_absolute():
        db_path = (REPO_ROOT / db_path).resolve()
    return db_path


def _gather_storage_targets(settings: Settings) -> list[Path]:
    targets: set[Path] = set()

    def add(path: Path | str | None) -> None:
        normalized = _normalize(path)
        if normalized is not None:
            targets.add(normalized)

    add(settings.documents_dir)
    add(settings.configs_dir)
    add(settings.venvs_dir)
    add(settings.runs_dir)
    add(settings.pip_cache_dir)

    pip_cache = _normalize(settings.pip_cache_dir)
    if pip_cache and _within_default_root(pip_cache):
        add(pip_cache.parent)

    sqlite_path = _resolve_sqlite_database_path(settings)
    if sqlite_path:
        add(sqlite_path)
        if _within_default_root(sqlite_path):
            add(sqlite_path.parent)

    return sorted(targets, key=lambda path: str(path))


def _describe_targets(targets: Iterable[Path]) -> None:
    print("Storage paths resolved from ADE settings:")
    for path in targets:
        status = "" if path.exists() else " (missing)"
        print(f"  - {path}{status}")


def _remove_path(path: Path) -> bool:
    try:
        exists = path.exists() or path.is_symlink()
        if not exists:
            return False
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True
    except FileNotFoundError:
        return False


def _cleanup_targets(targets: Iterable[Path]) -> list[tuple[Path, Exception]]:
    errors: list[tuple[Path, Exception]] = []
    removal_order = sorted(
        targets,
        key=lambda path: (len(path.parents), str(path)),
        reverse=True,
    )
    for path in removal_order:
        try:
            removed = _remove_path(path)
            action = "removed" if removed else "skipped"
            suffix = "" if removed else " (missing)"
            print(f"{action:>8}: {path}{suffix}")
        except Exception as exc:  # noqa: BLE001
            errors.append((path, exc))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete configured ADE storage directories and databases.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Run non-interactively (no confirmation prompt).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the paths that *would* be removed without deleting anything.",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    targets = _gather_storage_targets(settings)

    if not targets:
        print("No storage paths resolved from ADE settings.")
        return 0

    _describe_targets(targets)

    if args.dry_run:
        print("Dry run mode enabled; no paths were removed.")
        return 0

    if not args.yes:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print(
                "⚠️  confirmation required; re-run with --yes or `npm run reset:force`.",
            )
            return 2
        answer = input("Proceed with deletion? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("🛑 storage reset cancelled")
            return 2

    print("Removing storage paths...")
    errors = _cleanup_targets(targets)
    if errors:
        print("❌ storage reset incomplete:")
        for path, exc in errors:
            print(f"  - {path}: {exc}")
        return 1

    print("🧹 storage reset complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
