"""Service layer coordinating config metadata and package storage."""

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.features.users.models import User
from backend.app.shared.core.config import Settings

from .exceptions import (
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionNotFoundError,
    InvalidConfigManifestError,
)
from .models import Config, ConfigVersion
from .repository import ConfigsRepository
from .schemas import (
    ConfigCreateRequest,
    ConfigRecord,
    ConfigSummary,
    ConfigVersionCreateRequest,
    ConfigVersionRecord,
)
from .storage import ConfigStorage


class ConfigsService:
    """Manage config metadata, manifest validation, and on-disk packages."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repository = ConfigsRepository(session)
        self._storage = ConfigStorage(settings)

    async def list_configs(
        self,
        *,
        workspace_id: str,
        include_deleted: bool,
    ) -> list[ConfigSummary]:
        configs = await self._repository.list_configs(
            workspace_id=workspace_id,
            include_deleted=include_deleted,
        )
        state = await self._repository.get_workspace_state(workspace_id)
        active_lookup: dict[str, ConfigVersion | None] = {}
        if state and state.config_id:
            active_lookup[state.config_id] = state.config_version
        return [
            self._build_summary(config, active_lookup.get(config.id))
            for config in configs
        ]

    async def get_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        include_deleted_versions: bool,
    ) -> ConfigRecord:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        state = await self._repository.get_workspace_state(workspace_id)
        active = None
        if state and state.config_id == config.id:
            active = state.config_version
        versions = self._filter_versions(config.versions, include_deleted_versions)
        return self._build_record(config, versions, active)

    async def create_config(
        self,
        *,
        workspace_id: str,
        request: ConfigCreateRequest,
        actor: User | None,
    ) -> ConfigRecord:
        self._validate_manifest(request.manifest)
        archive_bytes = self._decode_archive(request.package.content)
        self._validate_package_contents(archive_bytes, request.manifest)

        existing = await self._repository.find_by_slug(
            workspace_id=workspace_id,
            slug=request.slug,
        )
        if existing and existing.deleted_at is None:
            raise ConfigSlugConflictError(request.slug)

        actor_id = self._actor_id(actor)
        config = await self._repository.create_config(
            workspace_id=workspace_id,
            slug=request.slug,
            title=request.title,
            description=request.description,
            actor_id=actor_id,
        )

        sequence = await self._repository.next_sequence(config_id=config.id)
        archive_name = self._archive_name(request.package.filename, sequence)
        manifest_hash = self._hash_manifest(request.manifest)
        package_hash = self._hash_bytes(archive_bytes)
        stored = self._storage.store(
            config_id=config.id,
            sequence=sequence,
            archive_name=archive_name,
            archive_bytes=archive_bytes,
            manifest=request.manifest,
        )
        version = await self._repository.create_version(
            config=config,
            label=f"v{sequence}",
            manifest=request.manifest,
            manifest_sha256=manifest_hash,
            package_sha256=package_hash,
            package_uri=str(stored.package_dir),
            actor_id=actor_id,
            sequence=sequence,
        )
        await self._repository.touch_workspace_state(
            workspace_id=workspace_id,
            config_id=config.id,
            config_version_id=version.id,
            actor_id=actor_id,
        )
        await self._session.commit()
        refreshed = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config.id,
            include_deleted=True,
        )
        if refreshed is None:
            raise ConfigNotFoundError(config.id)
        state = await self._repository.get_workspace_state(workspace_id)
        active = state.config_version if state and state.config_id == refreshed.id else None
        versions = self._filter_versions(refreshed.versions, include_deleted=False)
        return self._build_record(refreshed, versions, active)

    async def publish_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        request: ConfigVersionCreateRequest,
        actor: User | None,
    ) -> ConfigVersionRecord:
        self._validate_manifest(request.manifest)
        archive_bytes = self._decode_archive(request.package.content)
        self._validate_package_contents(archive_bytes, request.manifest)

        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None or config.deleted_at is not None:
            raise ConfigNotFoundError(config_id)

        sequence = await self._repository.next_sequence(config_id=config.id)
        archive_name = self._archive_name(request.package.filename, sequence)
        manifest_hash = self._hash_manifest(request.manifest)
        package_hash = self._hash_bytes(archive_bytes)
        stored = self._storage.store(
            config_id=config.id,
            sequence=sequence,
            archive_name=archive_name,
            archive_bytes=archive_bytes,
            manifest=request.manifest,
        )
        actor_id = self._actor_id(actor)
        version = await self._repository.create_version(
            config=config,
            label=request.label,
            manifest=request.manifest,
            manifest_sha256=manifest_hash,
            package_sha256=package_hash,
            package_uri=str(stored.package_dir),
            actor_id=actor_id,
            sequence=sequence,
        )
        await self._session.commit()
        await self._session.refresh(version)
        return self._build_version(version)

    async def list_versions(
        self,
        *,
        workspace_id: str,
        config_id: str,
        include_deleted: bool,
    ) -> list[ConfigVersionRecord]:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        versions = self._filter_versions(config.versions, include_deleted)
        return [self._build_version(version) for version in versions]

    async def activate_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor: User | None,
    ) -> ConfigRecord:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        version = await self._repository.get_version(
            config_id=config.id,
            config_version_id=config_version_id,
        )
        if version is None or version.deleted_at is not None:
            raise ConfigVersionNotFoundError(config_version_id)
        await self._repository.touch_workspace_state(
            workspace_id=workspace_id,
            config_id=config.id,
            config_version_id=version.id,
            actor_id=self._actor_id(actor),
        )
        await self._session.commit()
        state = await self._repository.get_workspace_state(workspace_id)
        active = state.config_version if state and state.config_id == config.id else None
        versions = self._filter_versions(config.versions, include_deleted=False)
        return self._build_record(config, versions, active)

    async def archive_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor: User | None,
    ) -> None:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        version = await self._repository.get_version(
            config_id=config.id,
            config_version_id=config_version_id,
        )
        if version is None:
            raise ConfigVersionNotFoundError(config_version_id)
        await self._repository.archive_version(version, self._actor_id(actor))
        state = await self._repository.get_workspace_state(workspace_id)
        if state and state.config_version_id == version.id:
            await self._repository.clear_workspace_state(workspace_id, self._actor_id(actor))
        await self._session.commit()

    async def restore_version(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor: User | None,
    ) -> ConfigVersionRecord:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        version = await self._repository.get_version(
            config_id=config.id,
            config_version_id=config_version_id,
        )
        if version is None:
            raise ConfigVersionNotFoundError(config_version_id)
        await self._repository.restore_version(version, self._actor_id(actor))
        await self._session.commit()
        await self._session.refresh(version)
        return self._build_version(version)

    async def archive_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor: User | None,
    ) -> None:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        await self._repository.archive_config(config, self._actor_id(actor))
        await self._repository.clear_workspace_state(workspace_id, self._actor_id(actor))
        await self._session.commit()

    async def restore_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor: User | None,
    ) -> ConfigRecord:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        await self._repository.restore_config(config, self._actor_id(actor))
        await self._session.commit()
        state = await self._repository.get_workspace_state(workspace_id)
        active = state.config_version if state and state.config_id == config.id else None
        versions = self._filter_versions(config.versions, include_deleted=False)
        return self._build_record(config, versions, active)

    def _build_summary(
        self,
        config: Config,
        active_version: ConfigVersion | None,
    ) -> ConfigSummary:
        payload: dict[str, Any] = {
            "config_id": config.id,
            "workspace_id": config.workspace_id,
            "slug": config.slug,
            "title": config.title,
            "description": config.description,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "deleted_at": config.deleted_at,
            "active_version": self._build_version(active_version),
        }
        return ConfigSummary.model_validate(payload)

    def _build_record(
        self,
        config: Config,
        versions: Iterable[ConfigVersion],
        active_version: ConfigVersion | None,
    ) -> ConfigRecord:
        summary = self._build_summary(config, active_version)
        versions_payload = [
            record
            for item in versions
            if (record := self._build_version(item)) is not None
        ]
        payload = summary.model_dump()
        payload["versions"] = [version.model_dump() for version in versions_payload]
        return ConfigRecord.model_validate(payload)

    def _build_version(self, version: ConfigVersion | None) -> ConfigVersionRecord | None:
        if version is None:
            return None
        return ConfigVersionRecord.model_validate(
            {
                "config_version_id": version.id,
                "sequence": version.sequence,
                "label": version.label,
                "manifest": version.manifest,
                "manifest_sha256": version.manifest_sha256,
                "package_sha256": version.package_sha256,
                "package_uri": version.package_uri,
                "created_at": version.created_at,
                "updated_at": version.updated_at,
                "deleted_at": version.deleted_at,
            }
        )

    def _filter_versions(
        self,
        versions: Iterable[ConfigVersion],
        include_deleted: bool,
    ) -> list[ConfigVersion]:
        if include_deleted:
            return list(versions)
        return [version for version in versions if version.deleted_at is None]

    def _validate_manifest(self, manifest: dict[str, Any]) -> None:
        target_fields = manifest.get("target_fields")
        if not isinstance(target_fields, list) or not all(isinstance(item, str) for item in target_fields):
            raise InvalidConfigManifestError("Manifest must include a target_fields list")
        engine = manifest.get("engine")
        if engine is not None and not isinstance(engine, dict):
            raise InvalidConfigManifestError("Manifest engine section must be an object when provided")

    def _validate_package_contents(
        self,
        archive_bytes: bytes,
        manifest: dict[str, Any],
    ) -> None:
        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            try:
                with archive.open("manifest.json") as stream:
                    packaged_manifest = json.load(stream)
            except KeyError as exc:
                raise InvalidConfigManifestError("Config package is missing manifest.json") from exc
        if packaged_manifest != manifest:
            raise InvalidConfigManifestError(
                "Manifest payload does not match manifest.json in the package",
            )

    def _hash_manifest(self, manifest: dict[str, Any]) -> str:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _hash_bytes(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _decode_archive(self, content: str) -> bytes:
        try:
            return base64.b64decode(content, validate=True)
        except Exception as exc:  # pragma: no cover - validation ensures base64 input
            raise InvalidConfigManifestError("Config package payload is not valid base64") from exc

    def _archive_name(self, filename: str, sequence: int) -> str:
        name = Path(filename).name or f"v{sequence:04d}.zip"
        return name

    def _actor_id(self, actor: User | None) -> str | None:
        return getattr(actor, "id", None)


__all__ = ["ConfigsService"]
