"""Service layer for configuration lifecycle operations."""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import fnmatch
import io
import mimetypes
import os
import secrets
import shutil
import zipfile
from collections import defaultdict
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
        self,
        *,
        workspace_id: str,
        config_id: str,
        prefix: str,
        depth: str,
        include: list[str] | None,
        exclude: list[str] | None,
        limit: int,
        page_token: str | None,
        sort: str,
        order: str,
    ) -> dict:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        index = await run_in_threadpool(_build_file_index, config_path)

        normalized_prefix, prefix_is_file = _normalize_prefix_argument(
            prefix,
            index["dir_paths"],
            index["file_paths"],
        )

        depth_limit = _coerce_depth(depth)
        offset = _decode_page_token(page_token)

        filtered = _filter_entries(
            index["entries"],
            normalized_prefix,
            prefix_is_file,
            depth_limit,
            include or [],
            exclude or [],
        )

        total_files = sum(1 for entry in filtered if entry["kind"] == "file")
        total_dirs = sum(1 for entry in filtered if entry["kind"] == "dir")

        sorted_entries = _sort_entries(filtered, sort, order)
        window = sorted_entries[offset : offset + limit]

        next_token = None
        if offset + limit < len(sorted_entries):
            next_token = _encode_page_token(offset + limit)

        fileset_hash = _compute_fileset_hash(sorted_entries)

        listing = {
            "workspace_id": workspace_id,
            "config_id": config_id,
            "status": configuration.status,
            "capabilities": {
                "editable": configuration.status == "draft",
                "can_create": configuration.status == "draft",
                "can_delete": configuration.status == "draft",
                "can_rename": configuration.status == "draft",
            },
            "root": normalized_prefix,
            "prefix": normalized_prefix,
            "depth": depth,
            "generated_at": utc_now(),
            "fileset_hash": fileset_hash,
            "summary": {"files": total_files, "directories": total_dirs},
            "limits": {
                "code_max_bytes": _MAX_FILE_SIZE,
                "asset_max_bytes": _MAX_ASSET_FILE_SIZE,
            },
            "count": len(window),
            "next_token": next_token,
            "entries": window,
        }
        return listing

    async def read_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        relative_path: str,
        include_content: bool = True,
    ) -> dict:
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        if not file_path.is_file():
            raise FileNotFoundError(relative_path)
        return await run_in_threadpool(_read_file_info, file_path, rel_path, include_content)

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

    async def rename_entry(
        self,
        *,
        workspace_id: str,
        config_id: str,
        source_path: str,
        dest_path: str,
        overwrite: bool,
        dest_if_match: str | None,
    ) -> dict:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, config_id)

        src_rel = _normalize_editable_path(source_path)
        dest_rel = _normalize_editable_path(dest_path)
        src_abs = _resolve_entry_path(config_path, src_rel)

        if not src_abs.exists():
            raise FileNotFoundError(source_path)

        src_is_dir = src_abs.is_dir()
        if src_is_dir:
            src_abs = _ensure_allowed_directory_path(config_path, src_rel)
            dest_abs = _ensure_allowed_directory_path(config_path, dest_rel)
        else:
            src_abs = _ensure_allowed_file_path(config_path, src_rel)
            dest_abs = _ensure_allowed_file_path(config_path, dest_rel)

        if src_abs == dest_abs:
            raise InvalidPathError("source_equals_destination")

        if dest_abs.exists():
            if src_is_dir or dest_abs.is_dir():
                raise DestinationExistsError()
            if not overwrite:
                raise DestinationExistsError()
            if not dest_if_match:
                raise PreconditionRequiredError()
            current_etag = _compute_file_etag(dest_abs) or ""
            if canonicalize_etag(dest_if_match) != current_etag:
                raise PreconditionFailedError(current_etag)
            dest_abs.unlink()

        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        src_abs.replace(dest_abs)

        stat = dest_abs.stat()
        etag = _compute_file_etag(dest_abs) if dest_abs.is_file() else ""

        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        return {
            "from": _stringify_path(src_rel, src_is_dir),
            "to": _stringify_path(dest_rel, src_is_dir),
            "size": stat.st_size if dest_abs.is_file() else 0,
            "mtime": _format_mtime(stat.st_mtime),
            "etag": etag,
        }

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


class InvalidPageTokenError(Exception):
    """Raised when pagination token cannot be decoded."""


class InvalidDepthError(Exception):
    """Raised when an unsupported depth parameter is supplied."""


class DestinationExistsError(Exception):
    """Raised when rename target exists without overwrite preconditions."""


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


def _build_file_index(config_path: Path) -> dict:
    entries: list[dict] = []
    dir_paths: set[str] = set()
    file_paths: set[str] = set()
    child_counts: dict[str, int] = defaultdict(int)

    def _register_entry(entry: dict) -> None:
        entries.append(entry)
        parent = entry["parent"]
        child_counts[parent] += 1
        if entry["kind"] == "dir":
            dir_paths.add(entry["path"])
            child_counts.setdefault(entry["path"], 0)
        else:
            file_paths.add(entry["path"])

    def _add_directory(rel_path: PurePosixPath) -> None:
        path_str = _format_directory_path(rel_path)
        if path_str in dir_paths:
            return
        if path_str == "src/":
            # do not expose the top-level src pseudo directory
            return
        full_path = config_path / rel_path.as_posix()
        stat = full_path.stat()
        entry = {
            "path": path_str,
            "name": _entry_name(path_str),
            "parent": _entry_parent(path_str),
            "kind": "dir",
            "depth": _compute_depth_value(path_str),
            "size": None,
            "mtime": _format_mtime(stat.st_mtime),
            "etag": None,
            "content_type": "inode/directory",
            "has_children": False,
        }
        _register_entry(entry)

    def _add_file(rel_path: PurePosixPath) -> None:
        path_str = rel_path.as_posix()
        if path_str in file_paths:
            return
        full_path = config_path / path_str
        if not full_path.is_file():
            return
        stat = full_path.stat()
        entry = {
            "path": path_str,
            "name": _entry_name(path_str),
            "parent": _entry_parent(path_str),
            "kind": "file",
            "depth": _compute_depth_value(path_str),
            "size": stat.st_size,
            "mtime": _format_mtime(stat.st_mtime),
            "etag": _compute_file_etag(full_path) or "",
            "content_type": mimetypes.guess_type(path_str)[0] or "application/octet-stream",
            "has_children": False,
        }
        _register_entry(entry)

    if not config_path.exists():
        return {"entries": [], "dir_paths": dir_paths, "file_paths": file_paths}

    for name in sorted(_ROOT_FILE_WHITELIST):
        rel = PurePosixPath(name)
        _add_file(rel)

    for dir_name in sorted(_ROOT_DIR_WHITELIST):
        rel_dir = PurePosixPath(dir_name)
        dir_path = config_path / rel_dir.as_posix()
        if dir_path.exists():
            _add_directory(rel_dir)

    for dirpath, dirnames, filenames in os.walk(config_path):
        rel_dir = PurePosixPath(os.path.relpath(dirpath, config_path))
        if rel_dir == PurePosixPath("."):
            rel_dir = PurePosixPath("")
        for name in list(dirnames):
            rel = (rel_dir / name) if rel_dir else PurePosixPath(name)
            if not _is_allowed_directory(rel) or name in _EXCLUDED_NAMES:
                dirnames.remove(name)
                continue
            _add_directory(rel)
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
                _add_file(rel)

    for entry in entries:
        if entry["kind"] == "dir":
            entry["has_children"] = child_counts.get(entry["path"], 0) > 0

    entries.sort(key=lambda item: item["path"])
    return {"entries": entries, "dir_paths": dir_paths, "file_paths": file_paths}


def _filter_entries(
    entries: list[dict],
    prefix: str,
    prefix_is_file: bool,
    depth_limit: int | None,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[dict]:
    if prefix_is_file:
        subset = [entry for entry in entries if entry["path"] == prefix]
    else:
        subset = [entry for entry in entries if not prefix or entry["path"].startswith(prefix)]

    if prefix and not prefix_is_file and prefix not in {entry["path"] for entry in subset}:
        # ensure the prefix directory itself is represented if it exists
        matching = [entry for entry in entries if entry["path"] == prefix]
        subset = matching + subset

    def _matches_include(path: str) -> bool:
        if not include_patterns:
            return True
        return any(fnmatch.fnmatch(path, pattern) for pattern in include_patterns)

    def _matches_exclude(path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in exclude_patterns)

    prefix_depth = -1 if prefix == "" else _compute_depth_value(prefix)

    filtered: list[dict] = []
    for entry in subset:
        path = entry["path"]
        if not _matches_include(path) or _matches_exclude(path):
            continue
        if depth_limit is not None and not prefix_is_file:
            rel_depth = _relative_depth(entry["depth"], prefix_depth)
            if rel_depth > depth_limit:
                continue
        filtered.append(entry)
    return filtered


def _sort_entries(entries: list[dict], sort: str, order: str) -> list[dict]:
    reverse = order == "desc"

    def _key(entry: dict):
        if sort == "name":
            return entry["name"]
        if sort == "mtime":
            return entry.get("mtime") or dt.datetime.fromtimestamp(0, tz=dt.UTC)
        if sort == "size":
            return entry.get("size") or 0
        return entry["path"]

    return sorted(entries, key=_key, reverse=reverse)


def _compute_fileset_hash(entries: list[dict]) -> str:
    digest = sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        token = f"{entry['path']}\x00{entry.get('etag') or ''}\x00{entry.get('size') or 0}"
        digest.update(token.encode("utf-8"))
    return digest.hexdigest()


def _normalize_prefix_argument(prefix: str, dir_paths: set[str], file_paths: set[str]) -> tuple[str, bool]:
    candidate = (prefix or "").strip()
    candidate = candidate.lstrip("/")
    if not candidate:
        return "", False
    if not candidate.endswith("/") and f"{candidate}/" in dir_paths:
        candidate = f"{candidate}/"
    if candidate in dir_paths:
        return candidate, False
    if candidate in file_paths:
        return candidate, True
    return candidate, candidate.endswith("/") and candidate in dir_paths


def _coerce_depth(value: str) -> int | None:
    if value not in {"0", "1", "infinity"}:
        raise InvalidDepthError
    if value == "infinity":
        return None
    return int(value)


def _encode_page_token(offset: int) -> str:
    data = str(offset).encode("ascii")
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode_page_token(token: str | None) -> int:
    if not token:
        return 0
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + padding).decode("ascii")
        value = int(decoded)
    except (ValueError, binascii.Error) as exc:
        raise InvalidPageTokenError from exc
    if value < 0:
        raise InvalidPageTokenError
    return value


def _relative_depth(entry_depth: int, prefix_depth: int) -> int:
    return entry_depth - prefix_depth - 1


def _format_directory_path(rel_path: PurePosixPath) -> str:
    path = rel_path.as_posix()
    if not path:
        return ""
    if not path.endswith("/"):
        path = f"{path}/"
    return path


def _entry_name(path: str) -> str:
    trimmed = path[:-1] if path.endswith("/") else path
    if not trimmed:
        return ""
    return trimmed.split("/")[-1]


def _entry_parent(path: str) -> str:
    trimmed = path[:-1] if path.endswith("/") else path
    if not trimmed or "/" not in trimmed:
        return ""
    parent = trimmed.rsplit("/", 1)[0]
    if parent:
        parent = f"{parent}/"
    return parent


def _compute_depth_value(path: str) -> int:
    if not path:
        return -1
    trimmed = path[:-1] if path.endswith("/") else path
    if not trimmed:
        return 0
    return trimmed.count("/")


def _resolve_entry_path(root: Path, rel_path: PurePosixPath) -> Path:
    return root / rel_path.as_posix()


def _stringify_path(rel_path: PurePosixPath, is_dir: bool) -> str:
    value = rel_path.as_posix()
    if is_dir and value and not value.endswith("/"):
        value = f"{value}/"
    return value


def _read_file_info(path: Path, rel_path: PurePosixPath, include_content: bool) -> dict:
    data = path.read_bytes() if include_content else None
    stat = path.stat()
    etag = _compute_hash(data) if data is not None else _compute_file_etag(path)
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
        index = _build_file_index(config_path)
        for entry in index["entries"]:
            if entry["kind"] != "file":
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


def _format_mtime(timestamp: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(timestamp, tz=dt.UTC)
