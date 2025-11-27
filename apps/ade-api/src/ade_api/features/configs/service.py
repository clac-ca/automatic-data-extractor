"""Service layer for configuration lifecycle operations."""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import fnmatch
import io
import logging
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

from ade_api.shared.core.logging import log_context
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.mixins import generate_ulid

from .etag import canonicalize_etag
from .exceptions import (
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStateError,
    ConfigurationNotFoundError,
    ConfigValidationFailedError,
)
from .models import Configuration, ConfigurationStatus
from .repository import ConfigurationsRepository
from .schemas import (
    ConfigSource,
    ConfigSourceClone,
    ConfigSourceTemplate,
    ConfigValidationIssue,
    ConfigVersionRecord,
)
from .storage import ConfigStorage

logger = logging.getLogger(__name__)

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


def _serialize_configuration_version(configuration: Configuration) -> ConfigVersionRecord:
    return ConfigVersionRecord(
        configuration_version_id=configuration.id,
        configuration_id=configuration.id,
        workspace_id=configuration.workspace_id,
        status=configuration.status,
        semver=(
            str(configuration.configuration_version)
            if configuration.configuration_version
            else None
        ),
        content_digest=configuration.content_digest,
        created_at=configuration.created_at,
        updated_at=configuration.updated_at,
        activated_at=configuration.activated_at,
        deleted_at=None,
    )


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
        logger.debug(
            "config.list.start",
            extra=log_context(workspace_id=workspace_id),
        )
        configs = list(await self._repo.list_for_workspace(workspace_id))
        logger.debug(
            "config.list.success",
            extra=log_context(workspace_id=workspace_id, count=len(configs)),
        )
        return configs

    async def list_configuration_versions(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> list[ConfigVersionRecord]:
        logger.debug(
            "config.versions.list.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        versions = [_serialize_configuration_version(configuration)]
        logger.debug(
            "config.versions.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                count=len(versions),
            ),
        )
        return versions

    async def get_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        logger.debug(
            "config.get.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        logger.debug(
            "config.get.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                status=configuration.status.value,
            ),
        )
        return configuration

    async def create_configuration(
        self,
        *,
        workspace_id: str,
        display_name: str,
        source: ConfigSource,
    ) -> Configuration:
        configuration_id = generate_ulid()
        logger.debug(
            "config.create.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                display_name=display_name,
                source_type=getattr(source, "type", None),
            ),
        )
        try:
            await self._materialize_source(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                source=source,
            )
        except ConfigSourceInvalidError:
            logger.warning(
                "config.create.source_invalid",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    display_name=display_name,
                    source_type=getattr(source, "type", None),
                ),
            )
            raise
        except Exception:
            logger.exception(
                "config.create.materialize_error",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    display_name=display_name,
                    source_type=getattr(source, "type", None),
                ),
            )
            await self._storage.delete_config(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                missing_ok=True,
            )
            raise

        record = Configuration(
            id=configuration_id,
            workspace_id=workspace_id,
            display_name=display_name,
            status=ConfigurationStatus.DRAFT,
            configuration_version=0,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)

        logger.info(
            "config.create.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                display_name=display_name,
                status=record.status.value,
            ),
        )
        return record

    async def clone_configuration(
        self,
        *,
        workspace_id: str,
        source_configuration_id: str,
        display_name: str,
    ) -> Configuration:
        logger.debug(
            "config.clone.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=source_configuration_id,
                display_name=display_name,
            ),
        )
        source = ConfigSourceClone(type="clone", configuration_id=source_configuration_id)
        config = await self.create_configuration(
            workspace_id=workspace_id,
            display_name=display_name,
            source=source,
        )
        logger.info(
            "config.clone.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=config.id,
                source_configuration_id=source_configuration_id,
                display_name=display_name,
            ),
        )
        return config

    async def validate_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> ValidationResult:
        logger.debug(
            "config.validate.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        issues, digest = await self._storage.validate_path(config_path)

        logger.info(
            "config.validate.completed",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                issue_count=len(issues),
                has_digest=bool(digest),
            ),
        )
        return ValidationResult(configuration=configuration, issues=issues, content_digest=digest)

    async def activate_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        logger.debug(
            "config.activate.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        issues, digest = await self._storage.validate_path(config_path)
        if issues:
            logger.warning(
                "config.activate.validation_failed",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    issue_count=len(issues),
                ),
            )
            raise ConfigValidationFailedError(issues)

        if configuration.status is ConfigurationStatus.DRAFT:
            configuration.configuration_version = (
                max(configuration.configuration_version or 0, 0) + 1
            )
            configuration.content_digest = digest
        elif configuration.status in {
            ConfigurationStatus.PUBLISHED,
            ConfigurationStatus.INACTIVE,
        }:
            if configuration.content_digest and configuration.content_digest != digest:
                logger.warning(
                    "config.activate.digest_mismatch",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                    ),
                )
                raise ConfigStateError("Configuration contents differ from published digest")
            if configuration.content_digest is None:
                configuration.content_digest = digest
        else:
            logger.warning(
                "config.activate.state_invalid",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    current_status=configuration.status.value,
                ),
            )
            raise ConfigStateError("Configuration is not activatable")

        await self._demote_active(workspace_id=workspace_id, exclude=configuration_id)

        configuration.status = ConfigurationStatus.ACTIVE
        configuration.content_digest = configuration.content_digest or digest
        configuration.activated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.activate.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                status=configuration.status.value,
                configuration_version=configuration.configuration_version,
            ),
        )
        return configuration

    async def publish_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        logger.debug(
            "config.publish.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )

        if configuration.status is not ConfigurationStatus.DRAFT:
            logger.warning(
                "config.publish.state_invalid",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    current_status=configuration.status.value,
                ),
            )
            raise ConfigStateError("Configuration must be a draft before publishing")

        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        issues, digest = await self._storage.validate_path(config_path)
        if issues:
            logger.warning(
                "config.publish.validation_failed",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    issue_count=len(issues),
                ),
            )
            raise ConfigValidationFailedError(issues)

        configuration.status = ConfigurationStatus.PUBLISHED
        configuration.configuration_version = max(configuration.configuration_version or 0, 0) + 1
        configuration.content_digest = digest
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.publish.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                status=configuration.status.value,
                configuration_version=configuration.configuration_version,
            ),
        )
        return configuration

    async def deactivate_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        logger.debug(
            "config.deactivate.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        if configuration.status == ConfigurationStatus.INACTIVE:
            logger.info(
                "config.deactivate.noop",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    status=configuration.status.value,
                ),
            )
            return configuration

        configuration.status = ConfigurationStatus.INACTIVE
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.deactivate.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                status=configuration.status.value,
            ),
        )
        return configuration

    async def list_files(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        prefix: str,
        depth: str,
        include: list[str] | None,
        exclude: list[str] | None,
        limit: int,
        page_token: str | None,
        sort: str,
        order: str,
    ) -> dict:
        logger.debug(
            "config.files.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                prefix=prefix,
                depth=depth,
                limit=limit,
                sort=sort,
                order=order,
            ),
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
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
            "configuration_id": configuration_id,
            "status": configuration.status,
            "capabilities": {
                "editable": configuration.status == ConfigurationStatus.DRAFT,
                "can_create": configuration.status == ConfigurationStatus.DRAFT,
                "can_delete": configuration.status == ConfigurationStatus.DRAFT,
                "can_rename": configuration.status == ConfigurationStatus.DRAFT,
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

        logger.info(
            "config.files.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                prefix=normalized_prefix,
                depth=depth,
                count=len(window),
                total_files=total_files,
                total_dirs=total_dirs,
            ),
        )
        return listing

    async def read_file(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        relative_path: str,
        include_content: bool = True,
    ) -> dict:
        logger.debug(
            "config.files.read.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                include_content=include_content,
            ),
        )
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        if not file_path.is_file():
            logger.warning(
                "config.files.read.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    path=relative_path,
                ),
            )
            raise FileNotFoundError(relative_path)
        info = await run_in_threadpool(_read_file_info, file_path, rel_path, include_content)
        logger.info(
            "config.files.read.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                size=info["size"],
            ),
        )
        return info

    async def write_file(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        relative_path: str,
        content: bytes,
        parents: bool,
        if_match: str | None,
        if_none_match: str | None,
    ) -> dict:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)
        size_limit = _MAX_ASSET_FILE_SIZE if _is_assets_path(rel_path) else _MAX_FILE_SIZE

        logger.debug(
            "config.files.write.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                content_size=len(content),
                size_limit=size_limit,
                parents=parents,
            ),
        )

        if len(content) > size_limit:
            logger.warning(
                "config.files.write.payload_too_large",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    path=relative_path,
                    content_size=len(content),
                    size_limit=size_limit,
                ),
            )
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

        logger.info(
            "config.files.write.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                size=result["size"],
                file_created=result["created"],
            ),
        )
        return result

    async def delete_file(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        relative_path: str,
        if_match: str | None,
    ) -> None:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        rel_path = _normalize_editable_path(relative_path)
        file_path = _ensure_allowed_file_path(config_path, rel_path)

        logger.debug(
            "config.files.delete.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
            ),
        )

        await run_in_threadpool(_delete_file_checked, file_path, if_match)
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.files.delete.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
            ),
        )

    async def create_directory(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        relative_path: str,
    ) -> Path:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        rel_path = _normalize_editable_path(relative_path)
        dir_path = _ensure_allowed_directory_path(config_path, rel_path)

        logger.debug(
            "config.directories.create.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
            ),
        )

        await run_in_threadpool(dir_path.mkdir, 0o755, True)
        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.directories.create.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
            ),
        )
        return dir_path

    async def delete_directory(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        relative_path: str,
        recursive: bool,
    ) -> None:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        rel_path = _normalize_editable_path(relative_path)
        dir_path = _ensure_allowed_directory_path(config_path, rel_path)

        logger.debug(
            "config.directories.delete.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                recursive=recursive,
            ),
        )

        if not dir_path.exists():
            logger.warning(
                "config.directories.delete.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    path=relative_path,
                ),
            )
            raise FileNotFoundError(relative_path)

        if recursive:
            await run_in_threadpool(shutil.rmtree, dir_path)
        else:
            await run_in_threadpool(dir_path.rmdir)

        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        logger.info(
            "config.directories.delete.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                path=relative_path,
                recursive=recursive,
            ),
        )

    async def rename_entry(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        source_path: str,
        dest_path: str,
        overwrite: bool,
        dest_if_match: str | None,
    ) -> dict:
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        _ensure_editable_status(configuration)
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)

        logger.debug(
            "config.entries.rename.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                source_path=source_path,
                dest_path=dest_path,
                overwrite=overwrite,
            ),
        )

        src_rel = _normalize_editable_path(source_path)
        dest_rel = _normalize_editable_path(dest_path)
        src_abs = _resolve_entry_path(config_path, src_rel)

        if not src_abs.exists():
            logger.warning(
                "config.entries.rename.source_not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    source_path=source_path,
                ),
            )
            raise FileNotFoundError(source_path)

        src_is_dir = src_abs.is_dir()
        if src_is_dir:
            src_abs = _ensure_allowed_directory_path(config_path, src_rel)
            dest_abs = _ensure_allowed_directory_path(config_path, dest_rel)
        else:
            src_abs = _ensure_allowed_file_path(config_path, src_rel)
            dest_abs = _ensure_allowed_file_path(config_path, dest_rel)

        if src_abs == dest_abs:
            logger.warning(
                "config.entries.rename.same_path",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    source_path=source_path,
                    dest_path=dest_path,
                ),
            )
            raise InvalidPathError("source_equals_destination")

        if dest_abs.exists():
            if src_is_dir or dest_abs.is_dir():
                logger.warning(
                    "config.entries.rename.dest_exists_dir",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        source_path=source_path,
                        dest_path=dest_path,
                    ),
                )
                raise DestinationExistsError()
            if not overwrite:
                logger.warning(
                    "config.entries.rename.dest_exists_no_overwrite",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        source_path=source_path,
                        dest_path=dest_path,
                    ),
                )
                raise DestinationExistsError()
            if not dest_if_match:
                logger.warning(
                    "config.entries.rename.dest_etag_missing",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        source_path=source_path,
                        dest_path=dest_path,
                    ),
                )
                raise PreconditionRequiredError()
            current_etag = _compute_file_etag(dest_abs) or ""
            if canonicalize_etag(dest_if_match) != current_etag:
                logger.warning(
                    "config.entries.rename.dest_etag_mismatch",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        source_path=source_path,
                        dest_path=dest_path,
                    ),
                )
                raise PreconditionFailedError(current_etag)
            dest_abs.unlink()

        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        src_abs.replace(dest_abs)

        stat = dest_abs.stat()
        etag = _compute_file_etag(dest_abs) if dest_abs.is_file() else ""

        configuration.updated_at = utc_now()
        await self._session.flush()
        await self._session.refresh(configuration)

        result = {
            "from": _stringify_path(src_rel, src_is_dir),
            "to": _stringify_path(dest_rel, src_is_dir),
            "size": stat.st_size if dest_abs.is_file() else 0,
            "mtime": _format_mtime(stat.st_mtime),
            "etag": etag,
        }

        logger.info(
            "config.entries.rename.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                source_path=source_path,
                dest_path=dest_path,
                size=result["size"],
            ),
        )
        return result

    async def export_zip(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> bytes:
        logger.debug(
            "config.export_zip.start",
            extra=log_context(workspace_id=workspace_id, configuration_id=configuration_id),
        )
        config_path = await self._storage.ensure_config_path(workspace_id, configuration_id)
        data = await run_in_threadpool(_build_zip_bytes, config_path)

        logger.info(
            "config.export_zip.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                archive_size=len(data),
            ),
        )
        return data

    async def _materialize_source(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        source: ConfigSource,
    ) -> None:
        if isinstance(source, ConfigSourceTemplate):
            logger.debug(
                "config.source.materialize.template",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    template_id=source.template_id,
                ),
            )
            await self._storage.materialize_from_template(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                template_id=source.template_id,
            )
            return

        if isinstance(source, ConfigSourceClone):
            logger.debug(
                "config.source.materialize.clone",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    source_configuration_id=source.configuration_id,
                ),
            )
            await self._storage.materialize_from_clone(
                workspace_id=workspace_id,
                source_configuration_id=source.configuration_id,
                new_configuration_id=configuration_id,
            )
            return

        logger.warning(
            "config.source.materialize.unsupported",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                source_type=getattr(source, "type", None),
            ),
        )
        raise ConfigSourceNotFoundError("Unsupported source reference")

    async def _demote_active(self, workspace_id: str, exclude: str) -> None:
        existing = await self._repo.get_active(workspace_id)
        if existing is None or existing.id == exclude:
            return
        logger.debug(
            "config.demote_active",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=existing.id,
                new_status=ConfigurationStatus.INACTIVE.value,
            ),
        )
        existing.status = ConfigurationStatus.INACTIVE
        await self._session.flush()

    async def _require_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        configuration = await self._repo.get(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        if configuration is None:
            logger.warning(
                "config.get.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                ),
            )
            raise ConfigurationNotFoundError(configuration_id)
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
