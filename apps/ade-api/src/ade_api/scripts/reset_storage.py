"""CLI to purge ADE storage directories and reset the database."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import MetaData, inspect
from sqlalchemy.engine import URL, make_url

from ade_api.db import build_engine

from ..settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[5]


def _normalize(path: Path | str | None) -> Path | None:
    if path in (None, "", "."):
        return None
    candidate = path if isinstance(path, Path) else Path(path)
    resolved = candidate.expanduser().resolve()
    if resolved == resolved.parent:
        return None
    return resolved


def _within_data_root(path: Path, data_root: Path) -> bool:
    try:
        path.relative_to(data_root)
    except ValueError:
        return False
    return True


def _gather_storage_targets(settings: Settings, database_url: URL) -> list[Path]:
    targets: set[Path] = set()

    def add(path: Path | str | None) -> None:
        normalized = _normalize(path)
        if normalized is not None:
            targets.add(normalized)

    add(settings.data_dir)
    add(settings.workspaces_dir)
    add(settings.venvs_dir)
    add(settings.pip_cache_dir)

    pip_cache = _normalize(settings.pip_cache_dir)
    if pip_cache and _within_data_root(pip_cache, settings.data_dir):
        add(pip_cache.parent)

    return sorted(targets, key=lambda path: str(path))


def _describe_targets(targets: Iterable[Path]) -> None:
    print("Storage paths resolved from ADE settings:")
    items = list(targets)
    if not items:
        print("  (none)")
        return
    for path in items:
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


def _describe_database_target(database_url: URL) -> None:
    backend = database_url.get_backend_name()
    rendered = database_url.render_as_string(hide_password=True)
    print("Database target:")
    print(f"  - {backend} database: {rendered}")


def _drop_all_tables(settings: Settings) -> int:
    engine = build_engine(settings)
    try:
        with engine.begin() as connection:
            inspector = inspect(connection)
            dropped = 0

            for schema in inspector.get_schema_names():
                if schema in {"information_schema", "pg_catalog"}:
                    continue
                metadata = MetaData(schema=schema)
                metadata.reflect(bind=connection, schema=schema)
                if metadata.tables:
                    dropped += len(metadata.tables)
                    metadata.drop_all(bind=connection)

            return dropped
    finally:
        engine.dispose()


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
    if not settings.database_url:
        raise RuntimeError("Database settings are required (set ADE_SQL_*).")
    database_url = make_url(settings.database_url)
    targets = _gather_storage_targets(settings, database_url)

    _describe_targets(targets)
    _describe_database_target(database_url)

    if args.dry_run:
        print("Dry run mode enabled; no database tables or paths were removed.")
        return 0

    if not args.yes:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print(
                "⚠️  confirmation required; re-run with --yes or `npm run reset:force`.",
            )
            return 2
        answer = input("Proceed with database reset and storage deletion? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("🛑 storage reset cancelled")
            return 2

    drop_error: Exception | None = None
    dropped_tables: int | None = None

    print("Dropping database tables...")
    try:
        dropped_tables = _drop_all_tables(settings)
    except Exception as exc:  # noqa: BLE001
        drop_error = exc

    if drop_error is None:
        if dropped_tables:
            print(f"🗑️  dropped {dropped_tables} table(s)")
        else:
            print("No tables found to drop.")

    if targets:
        print("Removing storage paths...")
        errors = _cleanup_targets(targets)
    else:
        errors = []

    if drop_error or errors:
        print("❌ storage reset incomplete:")
        if drop_error:
            print(f"  - database reset failed: {drop_error}")
        for path, exc in errors:
            print(f"  - {path}: {exc}")
        return 1

    print("🧹 storage reset complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
