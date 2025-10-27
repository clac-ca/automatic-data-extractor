"""Service layer for configuration versioning workflows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.shared.core.time import utc_now

from .exceptions import (
    ConfigNotFoundError,
    ConfigPublishConflictError,
    ConfigRevertUnavailableError,
    ConfigSlugConflictError,
    ConfigVersionNotFoundError,
    DraftFileConflictError,
    DraftFileNotFoundError,
    DraftVersionNotFoundError,
    ManifestValidationError,
)
from .models import Config, ConfigFile, ConfigVersion
from .schemas import (
    ConfigFileContent,
    ConfigFileSummary,
    ConfigRecord,
    ConfigVersionRecord,
    ManifestPatchRequest,
    ManifestResponse,
)

CONFIG_STATUS_DRAFT = "draft"
CONFIG_STATUS_PUBLISHED = "published"
CONFIG_STATUS_DEPRECATED = "deprecated"
DEFAULT_DRAFT_SEMVER = "draft"


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
) -> None:
    if not isinstance(manifest, Mapping):
        raise ManifestValidationError("Manifest must be an object")
    file_set = set(files)
    columns = manifest.get("columns", [])
    if not isinstance(columns, list):
        raise ManifestValidationError("Manifest columns must be a list")
    ordinals: list[int] = []
    missing_paths: set[str] = set()
    for column in columns:
        if not isinstance(column, Mapping):
            raise ManifestValidationError("Column entries must be objects")
        path = column.get("path")
        ordinal = column.get("ordinal")
        if path:
            if path not in file_set:
                missing_paths.add(path)
        if ordinal is not None:
            ordinals.append(int(ordinal))
    if missing_paths:
        missing = ", ".join(sorted(missing_paths))
        raise ManifestValidationError(f"Manifest references missing files: {missing}")
    duplicates = {value for value in ordinals if ordinals.count(value) > 1}
    if duplicates:
        dup = ", ".join(str(item) for item in sorted(duplicates))
        raise ManifestValidationError(f"Manifest contains duplicate ordinals: {dup}")


class ConfigService:
    """Expose operations for packages and versions."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_configs(self, *, workspace_id: str) -> list[ConfigRecord]:
        stmt = (
            select(Config)
            .where(Config.workspace_id == workspace_id)
            .options(selectinload(Config.versions))
            .order_by(Config.created_at.desc(), Config.id.desc())
        )
        result = await self._session.execute(stmt)
        configs = list(result.scalars().unique().all())
        return [self._to_config_record(config) for config in configs]

    async def get_config(self, *, workspace_id: str, config_id: str) -> ConfigRecord:
        config = await self._load_config(config_id=config_id, workspace_id=workspace_id)
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
        draft = ConfigVersion(
            config=config,
            semver=DEFAULT_DRAFT_SEMVER,
            status=CONFIG_STATUS_DRAFT,
            manifest_json=_dump_manifest(manifest),
            files_hash="",
            created_by=actor_id,
        )
        self._session.add(config)
        self._session.add(draft)

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

    async def delete_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        force: bool = False,
    ) -> None:
        config = await self._load_config(config_id=config_id, workspace_id=workspace_id)
        has_published = any(
            version.status == CONFIG_STATUS_PUBLISHED for version in config.versions
        )
        if has_published and not force:
            raise ConfigPublishConflictError("Cannot delete config with published versions")
        await self._session.delete(config)
        await self._session.flush()

    async def list_versions(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[ConfigVersionRecord]:
        config = await self._load_config(config_id=config_id, workspace_id=workspace_id)
        stmt = (
            select(ConfigVersion)
            .where(ConfigVersion.config_id == config.id)
            .order_by(ConfigVersion.created_at.desc(), ConfigVersion.id.desc())
        )
        result = await self._session.execute(stmt)
        versions = list(result.scalars().all())
        return [self._to_version_record(version) for version in versions]

    async def publish_draft(
        self,
        *,
        workspace_id: str,
        config_id: str,
        semver: str,
        message: str | None,
        actor_id: str | None = None,
    ) -> ConfigVersionRecord:
        config = await self._load_config(config_id=config_id, workspace_id=workspace_id)
        draft = self._get_draft_version(config)

        # ensure draft hash up to date
        await self._sync_draft_files_hash(draft)

        draft_files = await self._list_version_files(draft.id)
        manifest = _load_manifest(draft.manifest_json)
        _validate_manifest_payload(
            manifest,
            files=(file.path for file in draft_files),
        )

        if semver == DEFAULT_DRAFT_SEMVER:
            raise ConfigPublishConflictError("Semver must not reuse draft identifier")

        stmt = select(func.count()).select_from(ConfigVersion).where(
            ConfigVersion.config_id == config.id,
            ConfigVersion.semver == semver,
        )
        existing = await self._session.execute(stmt)
        if existing.scalar_one() > 0:
            raise ConfigPublishConflictError(f"Semver {semver!r} already exists for this config")

        manifest["files_hash"] = draft.files_hash

        now = utc_now()

        current_published = await self._get_current_published(config.id)
        if current_published is not None:
            current_published.status = CONFIG_STATUS_DEPRECATED
            await self._session.flush()

        published = ConfigVersion(
            config_id=config.id,
            semver=semver,
            status=CONFIG_STATUS_PUBLISHED,
            message=message,
            manifest_json=_dump_manifest(manifest),
            files_hash=draft.files_hash,
            created_by=actor_id,
            published_at=now,
        )
        self._session.add(published)
        await self._session.flush()
        await self._session.refresh(published)

        # copy files
        for file in draft_files:
            clone = ConfigFile(
                config_version_id=published.id,
                path=file.path,
                language=file.language,
                code=file.code,
                sha256=file.sha256,
            )
            self._session.add(clone)
        await self._session.flush()

        await self._session.refresh(published)
        return self._to_version_record(published)

    async def revert_published(
        self,
        *,
        workspace_id: str,
        config_id: str,
        message: str | None,
    ) -> ConfigVersionRecord:
        config = await self._load_config(config_id=config_id, workspace_id=workspace_id)
        current = await self._get_current_published(config.id)
        if current is None:
            raise ConfigRevertUnavailableError(config_id)

        stmt = (
            select(ConfigVersion)
            .where(
                ConfigVersion.config_id == config.id,
                ConfigVersion.status == CONFIG_STATUS_DEPRECATED,
            )
            .order_by(ConfigVersion.published_at.desc().nullslast())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        target = result.scalar_one_or_none()
        if target is None:
            raise ConfigRevertUnavailableError(config_id)

        now = utc_now()
        current.status = CONFIG_STATUS_DEPRECATED
        target.status = CONFIG_STATUS_PUBLISHED
        target.published_at = now
        if message:
            target.message = message
        await self._session.flush()
        await self._session.refresh(target)
        return self._to_version_record(target)

    async def _get_current_published(self, config_id: str) -> ConfigVersion | None:
        stmt = (
            select(ConfigVersion)
            .where(
                ConfigVersion.config_id == config_id,
                ConfigVersion.status == CONFIG_STATUS_PUBLISHED,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _list_version_files(self, config_version_id: str) -> list[ConfigFile]:
        stmt = (
            select(ConfigFile)
            .where(ConfigFile.config_version_id == config_version_id)
            .order_by(ConfigFile.path.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _sync_draft_files_hash(self, draft: ConfigVersion) -> str:
        files = await self._list_version_files(draft.id)
        files_hash = _files_hash_from_files(files)
        manifest = _load_manifest(draft.manifest_json)
        manifest["files_hash"] = files_hash
        draft.files_hash = files_hash
        draft.manifest_json = _dump_manifest(manifest)
        await self._session.flush()
        return files_hash

    async def _load_config(self, *, config_id: str, workspace_id: str) -> Config:
        stmt = (
            select(Config)
            .where(Config.id == config_id, Config.workspace_id == workspace_id)
            .options(selectinload(Config.versions))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        config = result.scalar_one_or_none()
        if config is None:
            raise ConfigNotFoundError(config_id)
        return config

    def _get_draft_version(self, config: Config) -> ConfigVersion:
        for version in config.versions:
            if version.status == CONFIG_STATUS_DRAFT:
                return version
        raise DraftVersionNotFoundError(str(config.id))

    def _to_config_record(self, config: Config) -> ConfigRecord:
        draft = None
        published = None
        for version in config.versions:
            if version.status == CONFIG_STATUS_DRAFT:
                draft = self._to_version_record(version)
            elif version.status == CONFIG_STATUS_PUBLISHED:
                published = self._to_version_record(version)
        return ConfigRecord(
            config_id=str(config.id),
            workspace_id=config.workspace_id,
            slug=config.slug,
            title=config.title,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            draft=draft,
            published=published,
        )

    def _to_version_record(self, version: ConfigVersion) -> ConfigVersionRecord:
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
            published_at=version.published_at,
            manifest=_load_manifest(version.manifest_json),
        )


class ConfigFileService:
    """Expose helpers for draft file manipulation."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_draft_files(
        self, *, workspace_id: str, config_id: str
    ) -> list[ConfigFileSummary]:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        files = await self._list_files(draft.id)
        return [self._to_file_summary(file) for file in files]

    async def get_draft_file(
        self, *, workspace_id: str, config_id: str, path: str
    ) -> ConfigFileContent:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        file = await self._get_file(draft.id, path)
        return self._to_file_content(file)

    async def create_draft_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
        code: str,
        language: str | None,
    ) -> ConfigFileContent:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        existing = await self._find_file(draft.id, path)
        if existing is not None:
            raise DraftFileConflictError(path)

        sha = _hash_code(code)
        file = ConfigFile(
            config_version_id=draft.id,
            path=path,
            language=language or "python",
            code=code,
            sha256=sha,
        )
        self._session.add(file)
        await self._session.flush()
        await self._session.refresh(file)

        await self._sync_draft_hash(draft.id)
        return self._to_file_content(file)

    async def update_draft_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
        code: str,
        expected_sha: str | None,
    ) -> ConfigFileContent:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        file = await self._get_file(draft.id, path)
        if expected_sha and expected_sha != file.sha256:
            raise DraftFileConflictError(path)
        file.code = code
        file.sha256 = _hash_code(code)
        await self._session.flush()
        await self._session.refresh(file)

        await self._sync_draft_hash(draft.id)
        return self._to_file_content(file)

    async def delete_draft_file(
        self, *, workspace_id: str, config_id: str, path: str
    ) -> None:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        file = await self._get_file(draft.id, path)
        await self._session.delete(file)
        await self._session.flush()
        await self._sync_draft_hash(draft.id)

    async def _load_draft(self, *, config_id: str, workspace_id: str) -> ConfigVersion:
        stmt = (
            select(ConfigVersion)
            .join(Config, Config.id == ConfigVersion.config_id)
            .where(
                Config.id == config_id,
                Config.workspace_id == workspace_id,
                ConfigVersion.status == CONFIG_STATUS_DRAFT,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftVersionNotFoundError(config_id)
        return draft

    async def _list_files(self, config_version_id: str) -> list[ConfigFile]:
        stmt = (
            select(ConfigFile)
            .where(ConfigFile.config_version_id == config_version_id)
            .order_by(ConfigFile.path.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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
            raise DraftFileNotFoundError(path)
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

    async def _sync_draft_hash(self, config_version_id: str) -> str:
        stmt = select(ConfigVersion).where(ConfigVersion.id == config_version_id).limit(1)
        result = await self._session.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftVersionNotFoundError(config_version_id)
        files = await self._list_files(config_version_id)
        files_hash = _files_hash_from_files(files)
        manifest = _load_manifest(draft.manifest_json)
        manifest["files_hash"] = files_hash
        draft.files_hash = files_hash
        draft.manifest_json = _dump_manifest(manifest)
        await self._session.flush()
        return files_hash

    def _to_file_summary(self, file: ConfigFile) -> ConfigFileSummary:
        return ConfigFileSummary(
            config_file_id=str(file.id),
            config_version_id=file.config_version_id,
            path=file.path,
            language=file.language,
            sha256=file.sha256,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    def _to_file_content(self, file: ConfigFile) -> ConfigFileContent:
        return ConfigFileContent(
            config_file_id=str(file.id),
            config_version_id=file.config_version_id,
            path=file.path,
            language=file.language,
            sha256=file.sha256,
            code=file.code,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )


class ManifestService:
    """Expose helpers for manifest read/write."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get_manifest(
        self, *, workspace_id: str, config_id: str
    ) -> ManifestResponse:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        manifest = _load_manifest(draft.manifest_json)
        return ManifestResponse(manifest=manifest)

    async def patch_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
        payload: ManifestPatchRequest,
    ) -> ManifestResponse:
        draft = await self._load_draft(config_id=config_id, workspace_id=workspace_id)
        manifest = _load_manifest(draft.manifest_json)
        manifest = _merge_manifest(manifest, payload.manifest)
        await self._validate_manifest(manifest, draft.id)
        # ensure hash stays in sync
        files_hash = await self._sync_draft_hash(draft.id)
        manifest["files_hash"] = files_hash
        draft.manifest_json = _dump_manifest(manifest)
        await self._session.flush()
        return ManifestResponse(manifest=manifest)

    async def _load_draft(self, *, config_id: str, workspace_id: str) -> ConfigVersion:
        stmt = (
            select(ConfigVersion)
            .join(Config, Config.id == ConfigVersion.config_id)
            .where(
                Config.id == config_id,
                Config.workspace_id == workspace_id,
                ConfigVersion.status == CONFIG_STATUS_DRAFT,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftVersionNotFoundError(config_id)
        return draft

    async def _sync_draft_hash(self, config_version_id: str) -> str:
        stmt = select(ConfigVersion).where(ConfigVersion.id == config_version_id).limit(1)
        result = await self._session.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftVersionNotFoundError(config_version_id)
        stmt_files = select(ConfigFile).where(ConfigFile.config_version_id == config_version_id)
        files_result = await self._session.execute(stmt_files)
        files = list(files_result.scalars().all())
        files_hash = _files_hash_from_files(files)
        draft.files_hash = files_hash
        await self._session.flush()
        return files_hash

    async def _validate_manifest(self, manifest: Mapping[str, Any], config_version_id: str) -> None:
        stmt = select(ConfigFile.path).where(ConfigFile.config_version_id == config_version_id)
        result = await self._session.execute(stmt)
        files = [row[0] for row in result.all()]
        _validate_manifest_payload(manifest, files=files)


__all__ = [
    "ConfigService",
    "ConfigFileService",
    "ManifestService",
]
