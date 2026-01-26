"""CLI to purge ADE storage (local paths + blob prefix) and reset the database."""

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


def _blob_prefix(settings: Settings) -> str:
    prefix = settings.blob_prefix.strip("/")
    return f"{prefix}/" if prefix else ""


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


def _describe_blob_target(settings: Settings) -> None:
    container = settings.blob_container or "(unset)"
    prefix = _blob_prefix(settings) or "(root)"
    print("Blob storage target:")
    print(f"  - container: {container}")
    print(f"  - prefix: {prefix}")
    if settings.blob_connection_string:
        print("  - auth: connection_string")
    elif settings.blob_account_url:
        print(f"  - auth: managed_identity ({settings.blob_account_url})")


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


def _build_blob_container_client(settings: Settings):
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Azure Blob dependencies are not installed. Install azure-identity and "
            "azure-storage-blob."
        ) from exc

    if not settings.blob_container:
        raise RuntimeError("ADE_BLOB_CONTAINER is required.")

    if settings.blob_connection_string:
        service = BlobServiceClient.from_connection_string(
            conn_str=settings.blob_connection_string
        )
    else:
        if not settings.blob_account_url:
            raise RuntimeError(
                "ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required."
            )
        service = BlobServiceClient(
            account_url=settings.blob_account_url,
            credential=DefaultAzureCredential(),
        )

    return service.get_container_client(settings.blob_container)


def _delete_blob_prefix(settings: Settings) -> tuple[int, list[Exception]]:
    errors: list[Exception] = []
    deleted = 0

    try:
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
    except ModuleNotFoundError:
        return 0, [
            RuntimeError(
                "Azure Blob dependencies are not installed. Install azure-identity and "
                "azure-storage-blob."
            )
        ]

    try:
        container_client = _build_blob_container_client(settings)
    except Exception as exc:  # noqa: BLE001
        return 0, [exc]

    try:
        container_client.get_container_properties()
    except ResourceNotFoundError:
        print("Blob container not found; skipping blob cleanup.")
        return 0, []
    except HttpResponseError as exc:
        return 0, [exc]

    prefix = _blob_prefix(settings)
    prefix_label = prefix or "(root)"
    print(f"Removing blobs under prefix: {prefix_label}")

    def _iter_blobs(include: list[str] | None) -> Iterable:
        try:
            if include:
                return container_client.list_blobs(name_starts_with=prefix, include=include)
            return container_client.list_blobs(name_starts_with=prefix)
        except TypeError:
            return container_client.list_blobs(name_starts_with=prefix)

    snapshot_iter = _iter_blobs(["snapshots"])
    try:
        for blob in snapshot_iter:
            snapshot = getattr(blob, "snapshot", None)
            if not snapshot:
                continue
            name = getattr(blob, "name", None) or str(blob)
            try:
                blob_client = container_client.get_blob_client(name, snapshot=snapshot)
                blob_client.delete_blob()
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
    except (HttpResponseError, ResourceNotFoundError) as exc:
        errors.append(exc)

    include_versions: list[str] | None = None
    if settings.blob_require_versioning:
        include_versions = ["versions", "deleted"]

    version_iter = _iter_blobs(include_versions)
    try:
        for blob in version_iter:
            name = getattr(blob, "name", None) or str(blob)
            version_id = getattr(blob, "version_id", None)
            try:
                blob_client = container_client.get_blob_client(name, version_id=version_id)
                delete_kwargs = {}
                if version_id is None:
                    delete_kwargs["delete_snapshots"] = "include"
                blob_client.delete_blob(**delete_kwargs)
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
    except (HttpResponseError, ResourceNotFoundError) as exc:
        errors.append(exc)

    if deleted:
        print(f"🗑️  deleted {deleted} blob item(s)")
    else:
        print("No blobs found to delete.")

    return deleted, errors


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
        description="Delete configured ADE storage (local paths + blob prefix) and databases.",
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
        raise RuntimeError("Database settings are required (set ADE_DATABASE_URL).")
    database_url = make_url(settings.database_url)
    targets = _gather_storage_targets(settings, database_url)

    _describe_targets(targets)
    _describe_blob_target(settings)
    _describe_database_target(database_url)

    if args.dry_run:
        print("Dry run mode enabled; no database tables, blob data, or paths were removed.")
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

    print("Removing blob storage...")
    _, blob_errors = _delete_blob_prefix(settings)

    if drop_error or errors or blob_errors:
        print("❌ storage reset incomplete:")
        if drop_error:
            print(f"  - database reset failed: {drop_error}")
        for path, exc in errors:
            print(f"  - {path}: {exc}")
        for exc in blob_errors:
            print(f"  - blob cleanup failed: {exc}")
        return 1

    print("🧹 storage reset complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
