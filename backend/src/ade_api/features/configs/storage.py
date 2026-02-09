"""Filesystem helper for config packages."""

from __future__ import annotations

import io
import secrets
import shutil
import zipfile
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import UUID

from ade_api.settings import Settings
from ade_storage import workspace_config_root

from .constants import (
    CONFIG_COPY_IGNORE_PATTERNS,
    CONFIG_DEP_FILES,
    CONFIG_EXCLUDED_NAMES,
    CONFIG_EXCLUDED_SUFFIXES,
    CONFIG_IGNORED_FILENAMES,
)
from .deps import ENGINE_DEPENDENCY_NAME, has_engine_dependency
from .exceptions import (
    ConfigEngineDependencyMissingError,
    ConfigImportError,
    ConfigPublishConflictError,
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
_IMPORT_MAX_EXPANDED_BYTES = 200 * 1024 * 1024  # 200 MiB safety cap
_IMPORT_MAX_ENTRIES = 5000
_IMPORT_DEFAULT_MAX_BYTES = 50 * 1024 * 1024
_IMPORT_ROOT_SENTINELS = {"src", "assets", *CONFIG_DEP_FILES}
_TEMPLATE_DIR_NAME = "default_config"


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
        template_root = self._template_root()
        if not template_root.is_dir():
            raise ConfigSourceNotFoundError("default_template_missing")

        workspace_root = self.workspace_root(workspace_id)
        destination = workspace_root / str(configuration_id)
        staging = workspace_root / f".init-{configuration_id}-{secrets.token_hex(4)}"

        workspace_root.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

        shutil.copytree(
            template_root,
            staging,
            ignore=shutil.ignore_patterns(*CONFIG_COPY_IGNORE_PATTERNS),
            copy_function=shutil.copyfile,
        )
        try:
            self._ensure_engine_dependency(staging)
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
        self._ensure_engine_dependency(path)
        return [], self.compute_config_digest(path)

    def compute_config_digest(self, path: Path) -> str:
        return _calculate_digest(path)

    def _template_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "templates" / _TEMPLATE_DIR_NAME

    def _ensure_engine_dependency(self, path: Path) -> None:
        if has_engine_dependency(path):
            return
        raise ConfigEngineDependencyMissingError(
            f"Configuration must declare {ENGINE_DEPENDENCY_NAME} in dependency manifests."
        )

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
        backup: Path | None = None

        workspace_root.mkdir(parents=True, exist_ok=True)

        try:
            max_bytes = self.import_max_bytes()
            if len(archive) > max_bytes:
                raise ConfigImportError("archive_too_large", limit=max_bytes)
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive, staging, max_bytes=max_bytes)
            self._ensure_engine_dependency(staging)

            if destination.exists():
                if not replace:
                    raise ConfigPublishConflictError(
                        f"Destination '{destination}' already exists"
                    )
                backup = (
                    workspace_root
                    / f".replace-backup-{configuration_id}-{secrets.token_hex(4)}"
                )
                if backup.exists():
                    shutil.rmtree(backup, ignore_errors=True)
                destination.replace(backup)

            try:
                staging.replace(destination)
            except Exception:
                if backup is not None and backup.exists() and not destination.exists():
                    backup.replace(destination)
                raise
            return None
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if backup is not None and backup.exists() and destination.exists():
                shutil.rmtree(backup, ignore_errors=True)

    def import_max_bytes(self) -> int:
        return self._import_max_bytes()

    def _import_max_bytes(self) -> int:
        if self._settings is None:
            return _IMPORT_DEFAULT_MAX_BYTES
        return self._settings.config_import_max_bytes

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
            self._ensure_engine_dependency(staging)
            if destination.exists():
                raise ConfigPublishConflictError(f"Destination '{destination}' already exists")
            staging.replace(destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

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


def _extract_archive(archive: bytes, destination: Path, *, max_bytes: int) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            entries = [info for info in zf.infolist() if not info.is_dir()]
            if not entries:
                raise ConfigImportError("archive_empty", detail="Archive contained no files")
            if len(entries) > _IMPORT_MAX_ENTRIES:
                raise ConfigImportError("too_many_entries", limit=_IMPORT_MAX_ENTRIES)

            infos: list[zipfile.ZipInfo] = []
            normalized_paths: list[PurePosixPath] = []
            for info in entries:
                rel_path = _normalize_archive_member(info.filename)
                if rel_path is None:
                    continue
                infos.append(info)
                normalized_paths.append(rel_path)

            if not normalized_paths:
                raise ConfigImportError("archive_empty", detail="Archive contained no files")

            rebased_paths = _strip_archive_wrappers(normalized_paths)
            destination_root = destination.resolve()
            total_uncompressed = 0

            for info, rel_path in zip(infos, rebased_paths, strict=True):
                if info.file_size > max_bytes:
                    raise ConfigImportError(
                        "file_too_large",
                        detail=rel_path.as_posix(),
                        limit=max_bytes,
                    )

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
    except zipfile.BadZipFile as exc:
        raise ConfigImportError(
            "invalid_archive",
            detail="Archive is not a valid zip file",
        ) from exc
    except (zipfile.LargeZipFile, RuntimeError, NotImplementedError) as exc:
        raise ConfigImportError(
            "invalid_archive",
            detail="Archive could not be read",
        ) from exc


def _normalize_archive_member(name: str) -> PurePosixPath | None:
    candidate = PurePosixPath(name.strip())
    parts = [part for part in candidate.parts if part not in (".", "")]
    if not parts:
        return None
    rel = PurePosixPath(*parts)
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise ConfigImportError("path_not_allowed", detail=name)
    if any(part in CONFIG_EXCLUDED_NAMES for part in rel.parts):
        return None
    if rel.name in CONFIG_IGNORED_FILENAMES:
        return None
    if rel.suffix in CONFIG_EXCLUDED_SUFFIXES:
        return None
    return rel


def _strip_archive_wrappers(paths: list[PurePosixPath]) -> list[PurePosixPath]:
    """Drop redundant top-level wrapper folders from archive members."""

    rebased = list(paths)
    while True:
        first_segments = {path.parts[0] for path in rebased if path.parts}
        if len(first_segments) != 1:
            return rebased
        segment = next(iter(first_segments))
        if segment in _IMPORT_ROOT_SENTINELS:
            return rebased
        if any(len(path.parts) <= 1 for path in rebased):
            return rebased
        rebased = [PurePosixPath(*path.parts[1:]) for path in rebased]


__all__ = ["ConfigStorage", "compute_config_digest"]


def compute_config_digest(root: Path) -> str:
    """Public helper to hash a configuration source tree (excluding .venv)."""

    return _calculate_digest(root)
