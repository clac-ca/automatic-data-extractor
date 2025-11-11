"""Service layer for configuration lifecycle operations."""

from __future__ import annotations

import datetime as dt
import io
import mimetypes
import os
import secrets
import shutil
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.shared.core.time import utc_now
from apps.api.app.shared.db.mixins import generate_ulid

from .etag import canonicalize_etag, format_etag
from .exceptions import (
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStateError,
    ConfigurationNotFoundError,
    ConfigValidationFailedError,
)
from .models import Configuration
from .repository import ConfigurationsRepository
from .schemas import (
    ConfigSource,
    ConfigSourceClone,
    ConfigSourceTemplate,
    ConfigValidationIssue,
)
from .storage import ConfigStorage

_ROOT_FILE_WHITELIST = {"manifest.json", "pyproject.toml", "config.env"}
_ROOT_DIR_WHITELIST = {"src/ade_config", "assets"}
_EXCLUDED_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
}
_EXCLUDED_SUFFIXES = {".pyc"}
_MAX_FILE_SIZE = 512 * 1024  # 512 KiB
_MAX_ASSET_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB


@dataclass(slots=True)
class ValidationResult:
    """Return value for validation requests."""

    configuration: Configuration
    issues: list[ConfigValidationIssue]
    content_digest: str | None


class ConfigurationsService:
    """Coordinate persistence, validation, and lifecycle operations."""

    def __init__(self, *, session: AsyncSession, storage: ConfigStorage) -> None:
        self._session = session
        self._repo = ConfigurationsRepository(session)
        self._storage = storage

    async def list_configurations(self, *, workspace_id: str) -> list[Configuration]:
        return list(await self._repo.list_for_workspace(workspace_id))

    async def get_configuration(
        self, *, workspace_id: str, config_id: str
    ) -> Configuration:
        return await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )

    async def create_configuration(
        self,
        *,
        workspace_id: str,
        display_name: str,
        source: ConfigSource,
    ) -> Configuration:
        config_id = generate_ulid()
        try:
            await self._materialize_source(
                workspace_id=workspace_id,
                config_id=config_id,
                source=source,
            )
        except ConfigSourceInvalidError:
            raise
        except Exception:
            await self._storage.delete_config(
                workspace_id=workspace_id,
                config_id=config_id,
                missing_ok=True,
            )
            raise

        record = Configuration(
            workspace_id=workspace_id,
            config_id=config_id,
            display_name=display_name,
            status="draft",
            config_version=0,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def clone_configuration(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        display_name: str,
    ) -> Configuration:
        source = ConfigSourceClone(type="clone", config_id=source_config_id)
        return await self.create_configuration(
            workspace_id=workspace_id,
            display_name=display_name,
            source=source,
        )

    async def validate_configuration(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> ValidationResult:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        issues, digest = await self._storage.validate_path(config_path)
        return ValidationResult(configuration=configuration, issues=issues, content_digest=digest)

    async def activate_configuration(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> Configuration:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if configuration.status not in {"draft", "inactive"}:
            raise ConfigStateError("Configuration is not activatable")

        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        issues, digest = await self._storage.validate_path(config_path)
        if issues:
            raise ConfigValidationFailedError(issues)

        await self._demote_active(workspace_id=workspace_id, exclude=config_id)

        configuration.status = "active"
        configuration.config_version = max(configuration.config_version or 0, 0) + 1
        configuration.content_digest = digest
        configuration.activated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def deactivate_configuration(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> Configuration:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if configuration.status == "inactive":
            return configuration
        configuration.status = "inactive"
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def list_files(
        self, *, workspace_id: str, config_id: str
    ) -> list[dict]:
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        return await run_in_threadpool(_build_tree_listing, config_path)

    async def read_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
    ) -> dict:
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        if not file_path.is_file():
            raise FileNotFoundError(relative_path)
        return await run_in_threadpool(_read_file_info, file_path, rel_path)

    async def write_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
        content: bytes,
        parents: bool,
        if_match: str | None,
        if_none_match: str | None,
    ) -> dict:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        size_limit = (
            _MAX_ASSET_FILE_SIZE if _is_assets_path(rel_path) else _MAX_FILE_SIZE
        )
        if len(content) > size_limit:
            raise PayloadTooLargeError(size_limit)

        result = await run_in_threadpool(
            _write_file_atomic,
            file_path,
            rel_path,
            content,
            parents,
            if_match,
            if_none_match,
        )
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)
        return result

    async def delete_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
        if_match: str | None,
    ) -> None:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        await run_in_threadpool(_delete_file_checked, file_path, if_match)
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

    async def create_directory(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
    ) -> Path:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        dir_path = _ensure_allowed_directory_path(config_path, rel_path)
        await run_in_threadpool(dir_path.mkdir, 0o755, True)
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)
        return dir_path

    async def delete_directory(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
        recursive: bool,
    ) -> None:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        dir_path = _ensure_allowed_directory_path(config_path, rel_path)
        if not dir_path.exists():
            raise FileNotFoundError(relative_path)
        if recursive:
            await run_in_threadpool(shutil.rmtree, dir_path)
        else:
            await run_in_threadpool(dir_path.rmdir)
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

    async def export_zip(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> bytes:
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        return await run_in_threadpool(_build_zip_bytes, config_path)

    async def _materialize_source(
        self,
        *,
        workspace_id: str,
        config_id: str,
        source: ConfigSource,
    ) -> None:
        if isinstance(source, ConfigSourceTemplate):
            await self._storage.materialize_from_template(
                workspace_id=workspace_id,
                config_id=config_id,
                template_id=source.template_id,
            )
            return

        if isinstance(source, ConfigSourceClone):
            await self._storage.materialize_from_clone(
                workspace_id=workspace_id,
                source_config_id=source.config_id,
                new_config_id=config_id,
            )
            return

        raise ConfigSourceNotFoundError("Unsupported source reference")

    async def _demote_active(self, workspace_id: str, exclude: str) -> None:
        existing = await self._repo.get_active(workspace_id)
        if existing is None or existing.config_id == exclude:
            return
        existing.status = "inactive"
        await self._session.flush()

    async def _require_configuration(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> Configuration:
        configuration = await self._repo.get(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(config_id)
        return configuration


__all__ = ["ConfigurationsService", "ValidationResult"]


class InvalidPathError(Exception):
    """Raised when a supplied path is malformed."""


class PathNotAllowedError(Exception):
    """Raised when a supplied path is outside the editable set."""


class PreconditionRequiredError(Exception):
    """Raised when ETag preconditions are missing."""


class PreconditionFailedError(Exception):
    """Raised when ETag preconditions fail."""

    def __init__(self, current_etag: str) -> None:
        super().__init__("precondition_failed")
        self.current_etag = current_etag


class PayloadTooLargeError(Exception):
    """Raised when the uploaded file exceeds the configured limit."""

    def __init__(self, limit: int) -> None:
        super().__init__("payload_too_large")
        self.limit = limit


def _ensure_editable_status(configuration: Configuration) -> None:
    if configuration.status != "draft":
        raise ConfigStateError("config_not_editable")


def _normalize_editable_path(path: str) -> PurePosixPath:
    candidate = (path or "").strip()
    if not candidate:
        raise InvalidPathError("path_required")
    normalized = PurePosixPath(candidate)
    if normalized.is_absolute():
        raise InvalidPathError("absolute_paths_not_allowed")
    if any(part in ("..", "") for part in normalized.parts):
        raise InvalidPathError("invalid_segments")
    return normalized


def _is_src_config_path(rel_path: PurePosixPath) -> bool:
    parts = rel_path.parts
    return len(parts) >= 2 and parts[0] == "src" and parts[1] == "ade_config"


def _is_assets_path(rel_path: PurePosixPath) -> bool:
    return len(rel_path.parts) >= 1 and rel_path.parts[0] == "assets"


def _is_allowed_directory(rel_path: PurePosixPath) -> bool:
    if rel_path == PurePosixPath(""):
        return True
    if rel_path.as_posix() == "src":
        return True
    if str(rel_path) in _ROOT_DIR_WHITELIST:
        return True
    if _is_src_config_path(rel_path):
        return True
    if _is_assets_path(rel_path):
        return True
    return False


def _ensure_allowed_file_path(root: Path, rel_path: PurePosixPath) -> Path:
    if any(part in _EXCLUDED_NAMES for part in rel_path.parts):
        raise PathNotAllowedError(f"{rel_path} is excluded")
    if rel_path.suffix in _EXCLUDED_SUFFIXES or rel_path.name == ".DS_Store":
        raise PathNotAllowedError(f"{rel_path} is excluded")
    if len(rel_path.parts) == 1 and rel_path.as_posix() in _ROOT_FILE_WHITELIST:
        return root / rel_path.as_posix()
    if _is_src_config_path(rel_path) or _is_assets_path(rel_path):
        return root / rel_path.as_posix()
    raise PathNotAllowedError(f"{rel_path} is outside editable roots")


def _ensure_allowed_directory_path(root: Path, rel_path: PurePosixPath) -> Path:
    if not _is_allowed_directory(rel_path):
        raise PathNotAllowedError(f"{rel_path} is outside editable roots")
    if any(part in _EXCLUDED_NAMES for part in rel_path.parts):
        raise PathNotAllowedError(f"{rel_path} is excluded")
    return root / rel_path.as_posix()


def _build_tree_listing(config_path: Path) -> list[dict]:
    if not config_path.exists():
        return []
    entries: list[dict] = []
    # Include root-level files and directories explicitly
    for name in sorted(_ROOT_FILE_WHITELIST):
        file_path = config_path / name
        if file_path.is_file():
            stat = file_path.stat()
            entries.append(
                {
                    "path": name,
                    "type": "file",
                    "size": stat.st_size,
                    "mtime": _format_mtime(stat.st_mtime),
                    "etag": format_etag(_compute_file_etag(file_path)) or '""',
                }
            )
    for dir_name in sorted(_ROOT_DIR_WHITELIST):
        dir_path = config_path / dir_name
        if dir_path.exists():
            entries.append({"path": dir_name, "type": "dir"})

    for dirpath, dirnames, filenames in os.walk(config_path):
        rel_dir = PurePosixPath(os.path.relpath(dirpath, config_path))
        if rel_dir == PurePosixPath("."):
            rel_dir = PurePosixPath("")
        # prune disallowed directories
        for name in list(dirnames):
            rel = (rel_dir / name) if rel_dir else PurePosixPath(name)
            if not _is_allowed_directory(rel) or name in _EXCLUDED_NAMES:
                dirnames.remove(name)
        if rel_dir and _is_allowed_directory(rel_dir) and rel_dir.as_posix() != "src":
            entries.append(
                {
                    "path": rel_dir.as_posix(),
                    "type": "dir",
                }
            )
        for filename in filenames:
            rel = (rel_dir / filename) if rel_dir else PurePosixPath(filename)
            if not rel_dir and rel.as_posix() in _ROOT_FILE_WHITELIST:
                continue
            if (
                rel.as_posix() in _ROOT_FILE_WHITELIST
                or _is_src_config_path(rel)
                or _is_assets_path(rel)
            ):
                if any(part in _EXCLUDED_NAMES for part in rel.parts):
                    continue
                if rel.suffix in _EXCLUDED_SUFFIXES or rel.name == ".DS_Store":
                    continue
                path = config_path / rel.as_posix()
                if not path.is_file():
                    continue
                stat = path.stat()
                entries.append(
                    {
                        "path": rel.as_posix(),
                        "type": "file",
                        "size": stat.st_size,
                        "mtime": _format_mtime(stat.st_mtime),
                        "etag": format_etag(_compute_file_etag(path)) or '""',
                    }
                )
    entries.sort(key=lambda item: item["path"])
    return entries


def _read_file_info(path: Path, rel_path: PurePosixPath) -> dict:
    data = path.read_bytes()
    stat = path.stat()
    etag = _compute_hash(data)
    content_type = mimetypes.guess_type(rel_path.as_posix())[0] or "application/octet-stream"
    return {
        "path": rel_path.as_posix(),
        "data": data,
        "etag": etag,
        "size": stat.st_size,
        "mtime": _format_mtime(stat.st_mtime),
        "content_type": content_type,
    }


def _write_file_atomic(
    path: Path,
    rel_path: PurePosixPath,
    content: bytes,
    parents: bool,
    if_match: str | None,
    if_none_match: str | None,
) -> dict:
    if not path.parent.exists():
        if parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            raise InvalidPathError("parent_missing")
    exists = path.exists()
    current_etag = _compute_file_etag(path) if exists else None
    if exists:
        if not if_match:
            raise PreconditionRequiredError()
        if canonicalize_etag(if_match) != current_etag:
            raise PreconditionFailedError(current_etag or "")
    else:
        if if_none_match != "*":
            raise PreconditionRequiredError()
    tmp_path = path.parent / f".tmp-{secrets.token_hex(8)}"
    with tmp_path.open("wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(path)
    stat = path.stat()
    etag = _compute_hash(content)
    return {
        "path": rel_path.as_posix(),
        "size": stat.st_size,
        "mtime": _format_mtime(stat.st_mtime),
        "etag": etag,
        "created": not exists,
    }


def _delete_file_checked(path: Path, if_match: str | None) -> None:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    if not if_match:
        raise PreconditionRequiredError()
    current = _compute_file_etag(path)
    if canonicalize_etag(if_match) != current:
        raise PreconditionFailedError(current or "")
    path.unlink()


def _build_zip_bytes(config_path: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        entries = _build_tree_listing(config_path)
        for entry in entries:
            if entry["type"] != "file":
                continue
            source = config_path / entry["path"]
            if source.is_file():
                archive.write(source, entry["path"])
    buffer.seek(0)
    return buffer.read()


def _compute_file_etag(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    with path.open("rb") as fh:
        digest = sha256(fh.read()).hexdigest()
    return f"sha256:{digest}"


def _compute_hash(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _format_mtime(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp, tz=dt.UTC).isoformat()
