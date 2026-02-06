"""Filesystem helper for config packages."""

from __future__ import annotations

import io
import secrets
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import UUID

from ade_api.settings import Settings
from ade_storage import workspace_config_root

from .constants import (
    CONFIG_COPY_IGNORE_PATTERNS,
    CONFIG_EXCLUDED_NAMES,
    CONFIG_EXCLUDED_SUFFIXES,
    CONFIG_IGNORED_FILENAMES,
)
from .exceptions import (
    ConfigImportError,
    ConfigPublishConflictError,
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStorageNotFoundError,
)
from .schemas import ConfigValidationIssue

_DIGEST_SUFFIXES = {
    ".py",
    ".toml",
    ".json",
    ".md",
    ".txt",
    ".rst",
    ".yml",
    ".yaml",
    ".csv",
}
_IMPORT_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024  # 50 MiB compressed cap
_IMPORT_MAX_EXPANDED_BYTES = 200 * 1024 * 1024  # 200 MiB safety cap
_IMPORT_MAX_ENTRIES = 5000
_IMPORT_CODE_MAX_BYTES = 512 * 1024  # mirror per-file limits used by write_file
_IMPORT_ASSET_MAX_BYTES = 5 * 1024 * 1024


class ConfigStorage:
    """Manage filesystem copies and validation for configurations."""

    def __init__(
        self,
        *,
        configs_root: Path | None = None,
        settings: Settings | None = None,
    ) -> None:
        if configs_root is None and settings is None:
            raise ValueError("ConfigStorage requires settings or configs_root")
        if configs_root is None:
            assert settings is not None
            base_root = settings.configs_dir
        else:
            base_root = configs_root
        self._configs_root = base_root.expanduser().resolve()
        self._settings = settings

    @property
    def configs_root(self) -> Path:
        return self._configs_root

    def workspace_root(self, workspace_id: UUID) -> Path:
        if self._settings is not None:
            return workspace_config_root(self._settings, workspace_id)
        return self._configs_root / str(workspace_id) / "config_packages"

    def config_path(self, workspace_id: UUID, configuration_id: UUID) -> Path:
        return self.workspace_root(workspace_id) / str(configuration_id)

    def materialize_from_template(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
    ) -> None:
        workspace_root = self.workspace_root(workspace_id)
        destination = workspace_root / str(configuration_id)
        staging = workspace_root / f".init-{configuration_id}-{secrets.token_hex(4)}"

        workspace_root.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

        try:
            self._run_engine_config_init(staging)
            issues, _ = self.validate_path(staging)
            if issues:
                raise ConfigSourceInvalidError(issues)
            if destination.exists():
                raise ConfigPublishConflictError(f"Destination '{destination}' already exists")
            staging.replace(destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def materialize_from_clone(
        self,
        *,
        workspace_id: UUID,
        source_configuration_id: UUID,
        new_configuration_id: UUID,
    ) -> None:
        source_path = self.config_path(workspace_id, source_configuration_id)
        exists = source_path.is_dir()
        if not exists:
            raise ConfigSourceNotFoundError(f"Configuration '{source_configuration_id}' not found")
        self._materialize_from_source(
            source=source_path,
            workspace_id=workspace_id,
            configuration_id=new_configuration_id,
        )

    def ensure_config_path(self, workspace_id: UUID, configuration_id: UUID) -> Path:
        path = self.config_path(workspace_id, configuration_id)
        exists = path.is_dir()
        if not exists:
            raise ConfigStorageNotFoundError(f"Configuration files missing for {configuration_id}")
        return path

    def import_archive(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        archive: bytes,
    ) -> str | None:
        """Materialize a configuration from a zip archive."""

        return self._materialize_from_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=archive,
            replace=False,
        )

    def replace_from_archive(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        archive: bytes,
    ) -> str | None:
        """Replace an existing configuration (draft-only) from a zip archive."""

        return self._materialize_from_archive(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            archive=archive,
            replace=True,
        )

    def delete_config(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        missing_ok: bool = True,
    ) -> None:
        path = self.config_path(workspace_id, configuration_id)
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            if not missing_ok:
                raise

    def validate_path(
        self,
        path: Path,
    ) -> tuple[list[ConfigValidationIssue], str | None]:
        command = [
            sys.executable,
            "-m",
            "ade_engine",
            "config",
            "validate",
            "--config-package",
            str(path),
            "--log-format",
            "text",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        issues: list[ConfigValidationIssue] = []
        if result.returncode != 0:
            message_src = result.stderr.strip() or result.stdout.strip()
            message = message_src.splitlines()[0] if message_src else "Config validation failed"
            issues.append(
                ConfigValidationIssue(
                    path=".",
                    message=message,
                )
            )
        digest = None if issues else _calculate_digest(path)
        return issues, digest

    def _materialize_from_archive(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        archive: bytes,
        replace: bool,
    ) -> str | None:
        workspace_root = self.workspace_root(workspace_id)
        destination = workspace_root / str(configuration_id)
        staging = workspace_root / f".import-{configuration_id}-{secrets.token_hex(4)}"

        workspace_root.mkdir(parents=True, exist_ok=True)

        try:
            if len(archive) > _IMPORT_MAX_ARCHIVE_BYTES:
                raise ConfigImportError("archive_too_large", limit=_IMPORT_MAX_ARCHIVE_BYTES)
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive, staging)
            issues, digest = self.validate_path(staging)
            if issues:
                raise ConfigSourceInvalidError(issues)

            if destination.exists():
                if not replace:
                    raise ConfigPublishConflictError(
                        f"Destination '{destination}' already exists"
                    )
                shutil.rmtree(destination, ignore_errors=True)
            staging.replace(destination)
            return digest
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _materialize_from_source(
        self,
        *,
        source: Path,
        workspace_id: UUID,
        configuration_id: UUID,
    ) -> None:
        workspace_root = self.workspace_root(workspace_id)
        destination = workspace_root / str(configuration_id)
        staging = workspace_root / f".staging-{configuration_id}-{secrets.token_hex(4)}"
        workspace_root.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(
            source,
            staging,
            ignore=shutil.ignore_patterns(*CONFIG_COPY_IGNORE_PATTERNS),
            copy_function=shutil.copyfile,
        )
        try:
            issues, _ = self.validate_path(staging)
            if issues:
                raise ConfigSourceInvalidError(issues)
            if destination.exists():
                raise ConfigPublishConflictError(f"Destination '{destination}' already exists")
            staging.replace(destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _run_engine_config_init(self, target_dir: Path) -> None:
        command = [
            sys.executable,
            "-m",
            "ade_engine",
            "config",
            "init",
            str(target_dir),
            "--package-name",
            "ade_config",
            "--layout",
            "src",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            message_src = result.stderr.strip() or result.stdout.strip()
            message = message_src.splitlines()[0] if message_src else "Config init failed"
            raise ConfigSourceInvalidError([ConfigValidationIssue(path=".", message=message)])


def _calculate_digest(root: Path) -> str:
    files = _collect_digest_files(root)
    digest = sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _collect_digest_files(root: Path) -> list[Path]:
    def _iter() -> Iterable[Path]:
        for path in root.rglob("*"):
            if ".venv" in path.parts:
                continue
            if path.is_file() and path.suffix.lower() in _DIGEST_SUFFIXES:
                yield path

    files = list(_iter())
    files.sort(key=lambda item: item.relative_to(root).as_posix())
    return files


def _extract_archive(archive: bytes, destination: Path) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise ConfigImportError(
            "invalid_archive",
            detail="Archive is not a valid zip file",
        ) from exc

    entries = [info for info in zf.infolist() if not info.is_dir()]
    if not entries:
        raise ConfigImportError("archive_empty", detail="Archive contained no files")

    total_uncompressed = 0
    entry_count = 0
    destination_root = destination.resolve()
    for info in entries:
        entry_count += 1
        if entry_count > _IMPORT_MAX_ENTRIES:
            raise ConfigImportError("too_many_entries", limit=_IMPORT_MAX_ENTRIES)

        rel_path = _normalize_archive_member(info.filename)
        if rel_path is None:
            continue

        limit = (
            _IMPORT_ASSET_MAX_BYTES
            if rel_path.parts and rel_path.parts[0] == "assets"
            else _IMPORT_CODE_MAX_BYTES
        )
        if info.file_size > limit:
            raise ConfigImportError("file_too_large", detail=rel_path.as_posix(), limit=limit)

        total_uncompressed += info.file_size
        if total_uncompressed > _IMPORT_MAX_EXPANDED_BYTES:
            raise ConfigImportError("archive_too_large", limit=_IMPORT_MAX_EXPANDED_BYTES)

        target = destination / rel_path.as_posix()
        resolved = target.resolve()
        if destination_root not in resolved.parents and resolved != destination_root:
            raise ConfigImportError("path_not_allowed", detail=rel_path.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)

    if total_uncompressed == 0:
        raise ConfigImportError("archive_empty", detail="Archive contained no files")


def _normalize_archive_member(name: str) -> PurePosixPath | None:
    candidate = PurePosixPath(name.strip())
    parts = [part for part in candidate.parts if part not in (".", "")]
    if not parts:
        return None
    rel = PurePosixPath(*parts)
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise ConfigImportError("path_not_allowed", detail=name)
    if rel.parts[0] in CONFIG_EXCLUDED_NAMES:
        return None
    if rel.name in CONFIG_IGNORED_FILENAMES:
        return None
    if rel.suffix in CONFIG_EXCLUDED_SUFFIXES:
        return None
    return rel


__all__ = ["ConfigStorage", "compute_config_digest"]


def compute_config_digest(root: Path) -> str:
    """Public helper to hash a configuration source tree (excluding .venv)."""

    return _calculate_digest(root)
