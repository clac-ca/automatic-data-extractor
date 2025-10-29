"""Service layer for configuration version management."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.features.documents.models import Document
from backend.app.shared.core.time import utc_now

from .exceptions import (
    ConfigDependentJobsError,
    ConfigInvariantViolationError,
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionActivationError,
    ConfigVersionDependentJobsError,
    ConfigVersionNotFoundError,
    ManifestValidationError,
    VersionFileConflictError,
    VersionFileNotFoundError,
)
from .models import Config, ConfigFile, ConfigVersion
from .schemas import (
    ConfigScriptContent,
    ConfigScriptCreateRequest,
    ConfigScriptSummary,
    ConfigScriptUpdateRequest,
    ConfigRecord,
    ConfigVersionCreateRequest,
    ConfigVersionRecord,
    ConfigVersionTestRequest,
    ConfigVersionTestResponse,
    ConfigVersionValidateResponse,
    ManifestPatchRequest,
    ManifestResponse,
)
from ..jobs.models import Job

CONFIG_STATUS_ACTIVE = "active"
CONFIG_STATUS_INACTIVE = "inactive"
_INITIAL_VERSION_SEMVER = "v1"


def _hash_code(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_manifest(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ManifestValidationError("Stored manifest cannot be decoded as JSON") from exc


def _dump_manifest(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))


def _default_manifest(*, title: str) -> dict[str, Any]:
    return {
        "name": title,
        "sdk_version": "0.1.0",
        "min_score": 1.0,
        "columns": [],
        "table": {
            "transform": {"path": "table/transform.py"},
            "validators": {"path": "table/validators.py"},
        },
        "hints": {
            "header_row": None,
            "header_row_contains": [],
            "sheets": {"include": [], "exclude": []},
        },
        "pins": {},
        "capabilities": {
            "allow_network": False,
            "allow_llm": False,
            "resources": {},
        },
        "files_hash": "",
    }


def _files_hash_from_files(files: Sequence[ConfigFile]) -> str:
    if not files:
        return ""
    sha = hashlib.sha256()
    for file in sorted(files, key=lambda item: item.path):
        sha.update(file.sha256.encode("utf-8"))
        sha.update(b"\0")
    return sha.hexdigest()


def _merge_manifest(base: dict[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = _merge_manifest(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_manifest_payload(
    manifest: Mapping[str, Any],
    *,
    files: Iterable[str],
) -> list[str]:
    problems: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["Manifest must be an object"]
    file_set = set(files)
    columns = manifest.get("columns", [])
    if not isinstance(columns, list):
        return ["Manifest columns must be a list"]
    ordinals: list[int] = []
    missing_paths: set[str] = set()
    for column in columns:
        if not isinstance(column, Mapping):
            problems.append("Column entries must be objects")
            continue
        path = column.get("path")
        ordinal = column.get("ordinal")
        if path and path not in file_set:
            missing_paths.add(path)
        if ordinal is not None:
            try:
                ordinals.append(int(ordinal))
            except (TypeError, ValueError):  # pragma: no cover - defensive
                problems.append(f"Column ordinal for {path!r} must be an integer")
    if missing_paths:
        problems.append(
            "Manifest references missing files: "
            + ", ".join(sorted(missing_paths))
        )
    duplicates = {value for value in ordinals if ordinals.count(value) > 1}
    if duplicates:
        dup = ", ".join(str(item) for item in sorted(duplicates))
        problems.append(f"Manifest contains duplicate ordinals: {dup}")
    return problems


class ConfigService:
    """Expose operations for configuration packages and versions."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_configs(
        self,
        *,
        workspace_id: str,
        include_deleted: bool = False,
    ) -> list[ConfigRecord]:
        stmt = (
            select(Config)
            .where(Config.workspace_id == workspace_id)
            .options(selectinload(Config.versions))
            .order_by(Config.created_at.desc(), Config.id.desc())
        )
        if not include_deleted:
            stmt = stmt.where(Config.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        configs = list(result.scalars().unique().all())
        return [self._to_config_record(config) for config in configs]

    async def get_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        include_deleted: bool = False,
    ) -> ConfigRecord:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=include_deleted,
        )
        await self._session.refresh(config, attribute_names=["versions"])
        return self._to_config_record(config)

    async def create_config(
        self,
        *,
        workspace_id: str,
        slug: str,
        title: str,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        manifest = _default_manifest(title=title)
        config = Config(
            workspace_id=workspace_id,
            slug=slug,
            title=title,
            created_by=actor_id,
        )
        initial_version = ConfigVersion(
            config=config,
            semver=_INITIAL_VERSION_SEMVER,
            status=CONFIG_STATUS_ACTIVE,
            manifest_json=_dump_manifest(manifest),
            files_hash="",
            created_by=actor_id,
            activated_at=utc_now(),
        )
        self._session.add(config)
        self._session.add(initial_version)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            message = str(exc.orig)
            if "configs.workspace_id" in message and "configs.slug" in message:
                raise ConfigSlugConflictError(slug) from exc
            raise
        await self._session.refresh(config, attribute_names=["versions"])
        return self._to_config_record(config)

    async def archive_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor_id: str | None = None,
    ) -> None:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=True,
        )
        if config.deleted_at is not None:
            return
        timestamp = utc_now()
        config.deleted_at = timestamp
        config.deleted_by = actor_id
        await self._session.flush()

    async def restore_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor_id: str | None = None,  # noqa: ARG002 - reserved for audit usage
    ) -> ConfigRecord:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=True,
        )
        if config.deleted_at is None:
            await self._session.refresh(config, attribute_names=["versions"])
            return self._to_config_record(config)
        config.deleted_at = None
        config.deleted_by = None
        await self._session.flush()
        await self._session.refresh(config, attribute_names=["versions"])
        return self._to_config_record(config)

    async def hard_delete_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> None:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=True,
        )
        await self._session.refresh(config, attribute_names=["versions"])
        version_ids = [str(version.id) for version in config.versions]
        job_counts = await self._job_counts_for_versions(version_ids)
        if job_counts:
            raise ConfigDependentJobsError(str(config.id), job_counts)
        await self._session.delete(config)
        await self._session.flush()

    async def list_versions(
        self,
        *,
        workspace_id: str,
        config_id: str,
        status: str | None = None,
        include_deleted: bool = False,
    ) -> list[ConfigVersionRecord]:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=include_deleted,
        )
        stmt = (
            select(ConfigVersion)
            .where(ConfigVersion.config_id == config.id)
            .order_by(ConfigVersion.created_at.desc(), ConfigVersion.id.desc())
        )
        if not include_deleted:
            stmt = stmt.where(ConfigVersion.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(ConfigVersion.status == status)
        result = await self._session.execute(stmt)
        versions = list(result.scalars().all())
        return [self._to_version_record(version) for version in versions]

    async def get_active_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> ConfigVersionRecord:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=False,
        )
        await self._session.refresh(config, attribute_names=["versions"])
        for version in config.versions:
            if version.status == CONFIG_STATUS_ACTIVE and version.deleted_at is None:
                return self._to_version_record(version)
        raise ConfigVersionNotFoundError(f"active::{config_id}")

    async def get_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        include_deleted: bool = False,
    ) -> ConfigVersionRecord:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=include_deleted,
        )
        await self._session.refresh(version)
        return self._to_version_record(version)

    async def create_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        payload: ConfigVersionCreateRequest,
        actor_id: str | None = None,
    ) -> ConfigVersionRecord:
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=False,
        )
        source_manifest: dict[str, Any] | None = None
        files_to_clone: list[ConfigFile] = []
        if payload.source_version_id:
            source_version = await self._load_version(
                workspace_id=workspace_id,
                config_id=config_id,
                config_version_id=payload.source_version_id,
                include_deleted=False,
                eager_files=True,
            )
            source_manifest = _load_manifest(source_version.manifest_json)
            files_to_clone = list(source_version.files or [])
        elif payload.seed_defaults:
            source_manifest = _default_manifest(title=config.title)
        else:
            source_manifest = _default_manifest(title=config.title)

        version = ConfigVersion(
            config_id=config.id,
            semver=payload.semver,
            status=CONFIG_STATUS_INACTIVE,
            message=payload.message,
            manifest_json=_dump_manifest(source_manifest or {}),
            files_hash="",
            created_by=actor_id,
        )
        self._session.add(version)
        await self._session.flush()
        if files_to_clone:
            await self._clone_files(version.id, files_to_clone)
            await self._refresh_files_hash(version.id)
        await self._session.refresh(version, attribute_names=["files"])
        return self._to_version_record(version)

    async def clone_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        payload: ConfigVersionCreateRequest,
        actor_id: str | None = None,
    ) -> ConfigVersionRecord:
        await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
        )
        clone_payload = ConfigVersionCreateRequest(
            semver=payload.semver,
            message=payload.message,
            source_version_id=payload.source_version_id or config_version_id,
            seed_defaults=False,
        )
        return await self.create_version(
            workspace_id=workspace_id,
            config_id=config_id,
            payload=clone_payload,
            actor_id=actor_id,
        )

    async def activate_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor_id: str | None = None,
    ) -> ConfigVersionRecord:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
            eager_files=True,
        )
        if version.status == CONFIG_STATUS_ACTIVE:
            return self._to_version_record(version)
        manifest = _load_manifest(version.manifest_json)
        problems = _validate_manifest_payload(
            manifest,
            files=[file.path for file in version.files or []],
        )
        if problems:
            message = "Version cannot be activated until validation passes."
            raise ConfigVersionActivationError(message)
        # ensure config is not archived
        config = await self._load_config(
            config_id=config_id,
            workspace_id=workspace_id,
            include_deleted=False,
        )
        await self._session.refresh(config, attribute_names=["versions"])
        now = utc_now()
        for candidate in config.versions:
            if candidate.id == version.id or candidate.deleted_at is not None:
                continue
            if candidate.status == CONFIG_STATUS_ACTIVE:
                candidate.status = CONFIG_STATUS_INACTIVE
        await self._session.flush()
        version.status = CONFIG_STATUS_ACTIVE
        version.activated_at = now
        await self._session.flush()
        await self._session.refresh(version)
        return self._to_version_record(version)

    async def archive_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor_id: str | None = None,
    ) -> None:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=True,
        )
        if version.deleted_at is not None:
            return
        if version.status == CONFIG_STATUS_ACTIVE:
            raise ConfigInvariantViolationError(
                "Deactivate the version before archiving it."
            )
        version.deleted_at = utc_now()
        version.deleted_by = actor_id
        await self._session.flush()

    async def restore_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
    ) -> ConfigVersionRecord:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=True,
        )
        if version.deleted_at is None:
            return self._to_version_record(version)
        version.deleted_at = None
        version.deleted_by = None
        await self._session.flush()
        await self._session.refresh(version)
        return self._to_version_record(version)

    async def hard_delete_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
    ) -> None:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=True,
        )
        if version.status == CONFIG_STATUS_ACTIVE:
            raise ConfigInvariantViolationError(
                "Deactivate the version before deleting permanently."
            )
        if version.deleted_at is None:
            raise ConfigInvariantViolationError(
                "Archive the version before deleting permanently."
            )
        job_counts = await self._job_counts_for_versions([str(version.id)])
        count = job_counts.get(str(version.id), 0)
        if count:
            raise ConfigVersionDependentJobsError(str(version.id), count)
        await self._session.delete(version)
        await self._session.flush()

    async def validate_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
    ) -> ConfigVersionValidateResponse:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
            eager_files=True,
        )
        manifest = _load_manifest(version.manifest_json)
        problems = _validate_manifest_payload(
            manifest,
            files=[file.path for file in version.files or []],
        )
        return ConfigVersionValidateResponse(
            files_hash=version.files_hash,
            ready=not problems,
            problems=problems,
        )

    async def test_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        payload: ConfigVersionTestRequest,
    ) -> ConfigVersionTestResponse:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
        )
        await self._ensure_document_exists(
            workspace_id=workspace_id,
            document_id=payload.document_id,
        )
        summary = "Test execution not yet implemented."
        if payload.notes:
            summary = payload.notes
        return ConfigVersionTestResponse(
            files_hash=version.files_hash,
            document_id=payload.document_id,
            findings=[],
            summary=summary,
        )

    async def list_scripts(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
    ) -> list[ConfigScriptSummary]:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
            eager_files=True,
        )
        return [self._to_script_summary(file) for file in version.files or []]

    async def get_script(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        path: str,
    ) -> ConfigScriptContent:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
        )
        file = await self._get_file(version.id, path)
        return self._to_script_content(file)

    async def create_script(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        payload: ConfigScriptCreateRequest,
    ) -> ConfigScriptContent:
        version = await self._load_version_for_edit(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
        path = payload.path
        existing = await self._find_file(version.id, path)
        if existing is not None:
            raise VersionFileConflictError(path)
        file = ConfigFile(
            config_version_id=version.id,
            path=path,
            language=payload.language or "python",
            code=payload.template or "",
            sha256=_hash_code(payload.template or ""),
        )
        self._session.add(file)
        await self._session.flush()
        await self._refresh_files_hash(version.id)
        await self._session.refresh(file)
        return self._to_script_content(file)

    async def update_script(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        path: str,
        payload: ConfigScriptUpdateRequest,
        expected_sha: str | None,
    ) -> ConfigScriptContent:
        version = await self._load_version_for_edit(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
        file = await self._get_file(version.id, path)
        if expected_sha and expected_sha != file.sha256:
            raise VersionFileConflictError(path)
        file.code = payload.code
        file.sha256 = _hash_code(payload.code)
        await self._session.flush()
        await self._refresh_files_hash(version.id)
        await self._session.refresh(file)
        return self._to_script_content(file)

    async def delete_script(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        path: str,
    ) -> None:
        version = await self._load_version_for_edit(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
        file = await self._get_file(version.id, path)
        await self._session.delete(file)
        await self._session.flush()
        await self._refresh_files_hash(version.id)

    async def get_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
    ) -> tuple[ManifestResponse, str]:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
        )
        manifest = _load_manifest(version.manifest_json)
        return ManifestResponse(manifest=manifest), self._manifest_etag(version)

    async def update_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        payload: ManifestPatchRequest,
        expected_etag: str,
    ) -> tuple[ManifestResponse, str]:
        version = await self._load_version_for_edit(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            eager_files=False,
        )
        current_etag = self._manifest_etag(version)
        if current_etag != expected_etag:
            raise ConfigInvariantViolationError("Manifest has changed since it was retrieved.")
        manifest = _load_manifest(version.manifest_json)
        manifest = _merge_manifest(manifest, payload.manifest)
        files = await self.list_scripts(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
        # Manifest updates may introduce inconsistencies; these are surfaced via
        # validation rather than blocking optimistic edits.
        _validate_manifest_payload(
            manifest,
            files=[file.path for file in files],
        )
        manifest["files_hash"] = version.files_hash
        version.manifest_json = _dump_manifest(manifest)
        await self._session.flush()
        return ManifestResponse(manifest=manifest), self._manifest_etag(version)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _clone_files(
        self,
        config_version_id: str,
        files: Sequence[ConfigFile],
    ) -> None:
        for file in files:
            clone = ConfigFile(
                config_version_id=config_version_id,
                path=file.path,
                language=file.language,
                code=file.code,
                sha256=file.sha256,
            )
            self._session.add(clone)
        await self._session.flush()

    async def _refresh_files_hash(self, config_version_id: str) -> str:
        stmt_version = (
            select(ConfigVersion)
            .where(ConfigVersion.id == config_version_id)
            .options(selectinload(ConfigVersion.files))
            .limit(1)
        )
        result = await self._session.execute(stmt_version)
        version = result.scalar_one_or_none()
        if version is None:
            raise ConfigVersionNotFoundError(config_version_id)
        files = list(version.files or [])
        files_hash = _files_hash_from_files(files)
        manifest = _load_manifest(version.manifest_json)
        manifest["files_hash"] = files_hash
        version.files_hash = files_hash
        version.manifest_json = _dump_manifest(manifest)
        await self._session.flush()
        return files_hash

    async def _job_counts_for_versions(self, version_ids: Sequence[str]) -> dict[str, int]:
        if not version_ids:
            return {}
        stmt = (
            select(Job.config_version_id, func.count())
            .where(Job.config_version_id.in_(version_ids))
            .group_by(Job.config_version_id)
        )
        result = await self._session.execute(stmt)
        return {str(row[0]): int(row[1]) for row in result.all()}

    async def _load_config(
        self,
        *,
        config_id: str,
        workspace_id: str,
        include_deleted: bool,
    ) -> Config:
        stmt = (
            select(Config)
            .where(Config.id == config_id, Config.workspace_id == workspace_id)
            .options(selectinload(Config.versions))
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(Config.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        config = result.scalars().unique().one_or_none()
        if config is None:
            raise ConfigNotFoundError(config_id)
        return config

    async def _load_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        include_deleted: bool,
        eager_files: bool = False,
    ) -> ConfigVersion:
        stmt = (
            select(ConfigVersion)
            .join(Config, Config.id == ConfigVersion.config_id)
            .where(
                Config.id == config_id,
                Config.workspace_id == workspace_id,
                ConfigVersion.id == config_version_id,
            )
            .limit(1)
        )
        if not include_deleted:
            stmt = stmt.where(
                Config.deleted_at.is_(None),
                ConfigVersion.deleted_at.is_(None),
            )
        if eager_files:
            stmt = stmt.options(selectinload(ConfigVersion.files))
        result = await self._session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise ConfigVersionNotFoundError(config_version_id)
        return version

    async def _load_version_for_edit(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        eager_files: bool = False,
    ) -> ConfigVersion:
        version = await self._load_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=False,
            eager_files=eager_files,
        )
        if version.status != CONFIG_STATUS_INACTIVE:
            raise ConfigVersionActivationError(
                "Only inactive versions can be modified."
            )
        return version

    async def _get_file(self, config_version_id: str, path: str) -> ConfigFile:
        stmt = (
            select(ConfigFile)
            .where(
                ConfigFile.config_version_id == config_version_id,
                ConfigFile.path == path,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        file = result.scalar_one_or_none()
        if file is None:
            raise VersionFileNotFoundError(path)
        return file

    async def _find_file(self, config_version_id: str, path: str) -> ConfigFile | None:
        stmt = (
            select(ConfigFile)
            .where(
                ConfigFile.config_version_id == config_version_id,
                ConfigFile.path == path,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _ensure_document_exists(self, *, workspace_id: str, document_id: str) -> None:
        stmt = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise ConfigInvariantViolationError(
                f"Document {document_id!r} not found in workspace"
            )

    def _to_config_record(self, config: Config) -> ConfigRecord:
        active_version = next(
            (
                version
                for version in config.versions
                if version.status == CONFIG_STATUS_ACTIVE and version.deleted_at is None
            ),
            None,
        )
        return ConfigRecord(
            config_id=str(config.id),
            workspace_id=config.workspace_id,
            slug=config.slug,
            title=config.title,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            deleted_at=config.deleted_at,
            deleted_by=config.deleted_by,
            active_version=self._to_version_record(active_version) if active_version else None,
            versions_count=sum(1 for version in config.versions if version.deleted_at is None),
        )

    def _to_version_record(self, version: ConfigVersion | None) -> ConfigVersionRecord | None:
        if version is None:
            return None
        return ConfigVersionRecord(
            config_version_id=str(version.id),
            config_id=version.config_id,
            semver=version.semver,
            status=version.status,
            message=version.message,
            files_hash=version.files_hash,
            created_at=version.created_at,
            updated_at=version.updated_at,
            created_by=version.created_by,
            deleted_at=version.deleted_at,
            deleted_by=version.deleted_by,
            activated_at=version.activated_at,
            manifest=_load_manifest(version.manifest_json),
        )

    def _to_script_summary(self, file: ConfigFile) -> ConfigScriptSummary:
        return ConfigScriptSummary(
            config_script_id=str(file.id),
            config_version_id=file.config_version_id,
            path=file.path,
            language=file.language,
            sha256=file.sha256,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    def _to_script_content(self, file: ConfigFile) -> ConfigScriptContent:
        return ConfigScriptContent(
            config_script_id=str(file.id),
            config_version_id=file.config_version_id,
            path=file.path,
            language=file.language,
            sha256=file.sha256,
            code=file.code,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    def _manifest_etag(self, version: ConfigVersion) -> str:
        return hashlib.sha256(version.manifest_json.encode("utf-8")).hexdigest()


__all__ = ["ConfigService"]
