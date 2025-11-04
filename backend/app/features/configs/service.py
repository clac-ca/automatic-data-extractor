"""Service layer coordinating config metadata and package storage."""

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.features.users.models import User
from backend.app.shared.core.config import Settings
from backend.app.shared.core.time import utc_now
from backend.app.shared.db import generate_ulid
from backend.app.features.configs.spec import (
    ConfigPackageValidator,
    Diagnostic,
    DiagnosticLevel,
    ManifestError,
    ManifestLoader,
    ManifestV1,
)

from .activation_env import (
    ActivationEnvironmentManager,
    ActivationError,
    ActivationMetadataStore,
)
from .exceptions import (
    ConfigActivationError,
    ConfigDraftConflictError,
    ConfigDraftFileTypeError,
    ConfigDraftNotFoundError,
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionNotFoundError,
    InvalidConfigManifestError,
)
from .models import Config, ConfigVersion
from .repository import ConfigsRepository
from .schemas import (
    ConfigDraftRecord,
    ConfigFileContent,
    ConfigFileUpdate,
    ConfigPackageEntry,
    ConfigRecord,
    ConfigSummary,
    ConfigVersionRecord,
)
from .storage import ConfigStorage, PackageFileMetadata


@dataclass(slots=True)
class DraftMetadata:
    """Filesystem-backed metadata describing a config draft."""

    draft_id: str
    config_id: str
    workspace_id: str
    base_config_version_id: str | None
    base_sequence: int | None
    manifest_sha256: str | None
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str | None
    updated_by_user_id: str | None
    last_published_version_id: str | None = None

    @classmethod
    def new(
        cls,
        *,
        draft_id: str,
        config_id: str,
        workspace_id: str,
        base_version_id: str | None,
        base_sequence: int | None,
        manifest_sha256: str | None,
        actor_id: str | None,
    ) -> "DraftMetadata":
        now = utc_now()
        return cls(
            draft_id=draft_id,
            config_id=config_id,
            workspace_id=workspace_id,
            base_config_version_id=base_version_id,
            base_sequence=base_sequence,
            manifest_sha256=manifest_sha256,
            created_at=now,
            updated_at=now,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "config_id": self.config_id,
            "workspace_id": self.workspace_id,
            "base_config_version_id": self.base_config_version_id,
            "base_sequence": self.base_sequence,
            "manifest_sha256": self.manifest_sha256,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by_user_id": self.created_by_user_id,
            "updated_by_user_id": self.updated_by_user_id,
            "last_published_version_id": self.last_published_version_id,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "DraftMetadata":
        def _parse_datetime(key: str) -> datetime:
            value = payload.get(key)
            if not value:
                return utc_now()
            return datetime.fromisoformat(value)

        return cls(
            draft_id=str(payload.get("draft_id")),
            config_id=str(payload.get("config_id")),
            workspace_id=str(payload.get("workspace_id")),
            base_config_version_id=payload.get("base_config_version_id"),
            base_sequence=payload.get("base_sequence"),
            manifest_sha256=payload.get("manifest_sha256"),
            created_at=_parse_datetime("created_at"),
            updated_at=_parse_datetime("updated_at"),
            created_by_user_id=payload.get("created_by_user_id"),
            updated_by_user_id=payload.get("updated_by_user_id"),
            last_published_version_id=payload.get("last_published_version_id"),
        )


class ConfigsService:
    """Manage config metadata, manifest validation, and on-disk packages."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repository = ConfigsRepository(session)
        self._storage = ConfigStorage(settings)
        self._manifest_loader = ManifestLoader()
        self._package_validator = ConfigPackageValidator()
        self._activation_store = ActivationMetadataStore(self._storage)
        self._activation_manager = ActivationEnvironmentManager(
            settings=settings,
            storage=self._storage,
            metadata_store=self._activation_store,
        )

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

    async def validate_package(
        self,
        *,
        manifest: dict[str, Any],
        package_bytes: bytes,
    ) -> list[Diagnostic]:
        manifest_model = self._load_manifest(manifest, context="Manifest payload failed validation")
        canonical_manifest = self._canonical_manifest(manifest_model)
        self._ensure_package_manifest_alignment(
            archive_bytes=package_bytes,
            canonical_manifest=canonical_manifest,
        )
        diagnostics = self._package_validator.validate_archive_bytes(
            manifest=manifest_model,
            archive_bytes=package_bytes,
        )
        return list(diagnostics)

    async def create_config(
        self,
        *,
        workspace_id: str,
        slug: str,
        title: str,
        manifest: dict[str, Any],
        package_filename: str,
        package_bytes: bytes,
        actor: User | None,
        description: str | None = None,
    ) -> ConfigRecord:
        manifest_model = self._load_manifest(manifest, context="Manifest payload failed validation")
        canonical_manifest = self._canonical_manifest(manifest_model)
        stored_manifest = self._manifest_for_storage(manifest_model)
        diagnostics = self._package_validator.validate_archive_bytes(
            manifest=manifest_model,
            archive_bytes=package_bytes,
        )
        self._ensure_no_validation_errors(diagnostics)
        self._ensure_package_manifest_alignment(
            archive_bytes=package_bytes,
            canonical_manifest=canonical_manifest,
        )

        existing = await self._repository.find_by_slug(
            workspace_id=workspace_id,
            slug=slug,
        )
        if existing and existing.deleted_at is None:
            raise ConfigSlugConflictError(slug)

        actor_id = self._actor_id(actor)
        config = await self._repository.create_config(
            workspace_id=workspace_id,
            slug=slug,
            title=title,
            description=description,
            actor_id=actor_id,
        )

        sequence = await self._repository.next_sequence(config_id=config.id)
        archive_name = self._archive_name(package_filename, sequence)
        stored = self._storage.store(
            config_id=config.id,
            sequence=sequence,
            archive_name=archive_name,
            archive_bytes=package_bytes,
            manifest=stored_manifest,
        )
        manifest_hash = self._hash_manifest(canonical_manifest)
        package_hash = self._storage.compute_package_hash(stored.archive_path)
        version = await self._repository.create_version(
            config=config,
            label=f"v{sequence}",
            manifest=stored_manifest,
            manifest_sha256=manifest_hash,
            package_sha256=package_hash,
            package_path=str(stored.package_dir),
            config_script_api_version=manifest_model.config_script_api_version,
            actor_id=actor_id,
            sequence=sequence,
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
        label: str | None,
        manifest: dict[str, Any],
        package_filename: str,
        package_bytes: bytes,
        actor: User | None,
    ) -> ConfigVersionRecord:
        manifest_model = self._load_manifest(manifest, context="Manifest payload failed validation")
        canonical_manifest = self._canonical_manifest(manifest_model)
        stored_manifest = self._manifest_for_storage(manifest_model)
        diagnostics = self._package_validator.validate_archive_bytes(
            manifest=manifest_model,
            archive_bytes=package_bytes,
        )
        self._ensure_no_validation_errors(diagnostics)
        self._ensure_package_manifest_alignment(
            archive_bytes=package_bytes,
            canonical_manifest=canonical_manifest,
        )

        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None or config.deleted_at is not None:
            raise ConfigNotFoundError(config_id)

        sequence = await self._repository.next_sequence(config_id=config.id)
        archive_name = self._archive_name(package_filename, sequence)
        stored = self._storage.store(
            config_id=config.id,
            sequence=sequence,
            archive_name=archive_name,
            archive_bytes=package_bytes,
            manifest=stored_manifest,
        )
        manifest_hash = self._hash_manifest(canonical_manifest)
        package_hash = self._storage.compute_package_hash(stored.archive_path)
        actor_id = self._actor_id(actor)
        version = await self._repository.create_version(
            config=config,
            label=label,
            manifest=stored_manifest,
            manifest_sha256=manifest_hash,
            package_sha256=package_hash,
            package_path=str(stored.package_dir),
            config_script_api_version=manifest_model.config_script_api_version,
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

    async def list_drafts(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[ConfigDraftRecord]:
        config = await self._get_config_or_error(workspace_id, config_id)
        draft_ids = self._storage.list_drafts(config.id)
        records: list[ConfigDraftRecord] = []
        for draft_id in draft_ids:
            metadata = self._load_draft_metadata(
                workspace_id=config.workspace_id,
                config_id=config.id,
                draft_id=draft_id,
            )
            records.append(self._build_draft_record(metadata))
        return records

    async def create_draft(
        self,
        *,
        workspace_id: str,
        config_id: str,
        base_config_version_id: str,
        actor: User | None,
    ) -> ConfigDraftRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        version = await self._repository.get_version(
            config_id=config.id,
            config_version_id=base_config_version_id,
        )
        if version is None or version.deleted_at is not None:
            raise ConfigVersionNotFoundError(base_config_version_id)
        package_dir = Path(version.package_path)
        if not package_dir.exists():
            raise ConfigVersionNotFoundError(base_config_version_id)

        draft_id = generate_ulid()
        actor_id = self._actor_id(actor)
        metadata = DraftMetadata.new(
            draft_id=draft_id,
            config_id=config.id,
            workspace_id=config.workspace_id,
            base_version_id=version.id,
            base_sequence=version.sequence,
            manifest_sha256=version.manifest_sha256,
            actor_id=actor_id,
        )
        try:
            self._storage.create_draft_from_source(
                config_id=config.id,
                draft_id=draft_id,
                source_package_dir=package_dir,
                metadata=metadata.to_json(),
            )
        except FileNotFoundError as exc:
            raise ConfigVersionNotFoundError(base_config_version_id) from exc
        return self._build_draft_record(metadata)

    async def get_draft(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
    ) -> ConfigDraftRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        metadata = self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        return self._build_draft_record(metadata)

    async def delete_draft(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
    ) -> None:
        config = await self._get_config_or_error(workspace_id, config_id)
        # Ensure draft exists before attempting deletion
        self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        self._storage.delete_draft(config.id, draft_id)

    async def list_draft_entries(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
    ) -> list[ConfigPackageEntry]:
        config = await self._get_config_or_error(workspace_id, config_id)
        self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        try:
            entries = self._storage.list_entries(package_dir)
        except FileNotFoundError as exc:
            raise ConfigDraftNotFoundError(draft_id) from exc
        return [self._build_package_entry(entry) for entry in entries]

    async def read_draft_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
        path: str,
    ) -> ConfigFileContent:
        config = await self._get_config_or_error(workspace_id, config_id)
        self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        try:
            content = self._storage.read_text(package_dir, path)
        except FileNotFoundError as exc:
            raise ConfigDraftNotFoundError(draft_id) from exc
        except UnicodeDecodeError as exc:
            raise ConfigDraftFileTypeError(path) from exc
        sha256 = self._hash_text(content, encoding="utf-8")
        return ConfigFileContent(
            path=path,
            encoding="utf-8",
            content=content,
            sha256=sha256,
        )

    async def write_draft_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
        path: str,
        payload: ConfigFileUpdate,
        actor: User | None,
    ) -> ConfigFileContent:
        config = await self._get_config_or_error(workspace_id, config_id)
        metadata = self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        encoding = payload.encoding or "utf-8"
        if payload.expected_sha256 is not None:
            try:
                current = self._storage.read_text(package_dir, path, encoding=encoding)
            except FileNotFoundError:
                raise ConfigDraftConflictError(path)
            except UnicodeDecodeError as exc:
                raise ConfigDraftFileTypeError(path) from exc
            current_hash = self._hash_text(current, encoding=encoding)
            if current_hash != payload.expected_sha256:
                raise ConfigDraftConflictError(path)
        try:
            self._storage.write_text(
                package_dir,
                path,
                payload.content,
                encoding=encoding,
            )
        except UnicodeEncodeError as exc:
            raise ConfigDraftFileTypeError(path) from exc

        new_hash = self._hash_text(payload.content, encoding=encoding)
        self._touch_draft_metadata(
            metadata=metadata,
            actor=self._actor_id(actor),
        )
        if path == "manifest.json":
            metadata.manifest_sha256 = new_hash
        self._save_draft_metadata(config.id, metadata)
        return ConfigFileContent(
            path=path,
            encoding=encoding,
            content=payload.content,
            sha256=new_hash,
        )

    async def delete_draft_entry(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
        path: str,
        actor: User | None,
    ) -> None:
        config = await self._get_config_or_error(workspace_id, config_id)
        metadata = self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        try:
            self._storage.delete_entry(package_dir, path)
        except FileNotFoundError as exc:
            raise ConfigDraftNotFoundError(draft_id) from exc
        self._touch_draft_metadata(
            metadata=metadata,
            actor=self._actor_id(actor),
        )
        if path == "manifest.json":
            metadata.manifest_sha256 = None
        self._save_draft_metadata(config.id, metadata)

    async def publish_draft(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
        label: str | None,
        actor: User | None,
    ) -> ConfigVersionRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        metadata = self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        try:
            manifest_text = self._storage.read_text(package_dir, "manifest.json")
        except FileNotFoundError as exc:
            raise InvalidConfigManifestError("Draft manifest.json is missing") from exc
        except UnicodeDecodeError as exc:
            raise InvalidConfigManifestError("Draft manifest.json must be UTF-8 encoded") from exc
        try:
            manifest_payload = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise InvalidConfigManifestError("Draft manifest.json is not valid JSON") from exc
        manifest_model = self._load_manifest(
            manifest_payload,
            context="Draft manifest failed validation",
        )
        diagnostics = self._package_validator.validate(
            manifest=manifest_model,
            package_dir=package_dir,
        )
        self._ensure_no_validation_errors(diagnostics)

        canonical_manifest = self._canonical_manifest(manifest_model)
        stored_manifest = self._manifest_for_storage(manifest_model)
        archive_bytes = self._storage.build_archive_bytes(package_dir)
        sequence = await self._repository.next_sequence(config_id=config.id)
        archive_name = self._archive_name(f"{draft_id}.zip", sequence)
        stored = self._storage.store(
            config_id=config.id,
            sequence=sequence,
            archive_name=archive_name,
            archive_bytes=archive_bytes,
            manifest=stored_manifest,
        )
        manifest_hash = self._hash_manifest(canonical_manifest)
        package_hash = self._storage.compute_package_hash(stored.archive_path)
        actor_id = self._actor_id(actor)
        version = await self._repository.create_version(
            config=config,
            label=label,
            manifest=stored_manifest,
            manifest_sha256=manifest_hash,
            package_sha256=package_hash,
            package_path=str(stored.package_dir),
            config_script_api_version=manifest_model.config_script_api_version,
            actor_id=actor_id,
            sequence=sequence,
        )
        await self._session.commit()
        await self._session.refresh(version)

        metadata.manifest_sha256 = manifest_hash
        metadata.last_published_version_id = version.id
        self._touch_draft_metadata(
            metadata=metadata,
            actor=actor_id,
        )
        self._save_draft_metadata(config.id, metadata)
        return self._build_version(version)

    async def export_draft_archive(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
    ) -> tuple[str, bytes]:
        config = await self._get_config_or_error(workspace_id, config_id)
        self._load_draft_metadata(
            workspace_id=config.workspace_id,
            config_id=config.id,
            draft_id=draft_id,
        )
        package_dir = self._draft_package_dir(config.id, draft_id)
        if not package_dir.exists():
            raise ConfigDraftNotFoundError(draft_id)
        archive_bytes = self._storage.build_archive_bytes(package_dir)
        filename = f"{config.slug}-{draft_id}.zip"
        return filename, archive_bytes

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

        manifest_model = self._manifest_loader.load(version.manifest)
        try:
            await self._activation_manager.ensure_environment(
                config=config,
                version=version,
                manifest=manifest_model,
            )
        except ActivationError as exc:
            raise ConfigActivationError(str(exc), diagnostics=getattr(exc, "diagnostics", [])) from exc

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
        payload = {
            "config_version_id": version.id,
            "sequence": version.sequence,
            "label": version.label,
            "manifest": version.manifest,
            "manifest_sha256": version.manifest_sha256,
            "package_sha256": version.package_sha256,
            "package_path": version.package_path,
            "config_script_api_version": version.config_script_api_version,
            "created_at": version.created_at,
            "updated_at": version.updated_at,
            "deleted_at": version.deleted_at,
        }
        activation = self._activation_store.load(config_id=version.config_id, version=version)
        if activation is not None:
            payload["activation"] = {
                "status": activation.status,
                "started_at": activation.started_at,
                "completed_at": activation.completed_at,
                "error": activation.error,
                "venv_path": activation.venv_path.as_posix() if activation.venv_path else None,
                "python_executable": (
                    activation.python_executable.as_posix() if activation.python_executable else None
                ),
                "packages_uri": activation.packages_path.as_posix() if activation.packages_path else None,
                "install_log_uri": activation.install_log_path.as_posix()
                if activation.install_log_path
                else None,
                "hooks_uri": activation.hooks_path.as_posix() if activation.hooks_path else None,
                "diagnostics": activation.diagnostics,
                "annotations": activation.annotations,
            }
        return ConfigVersionRecord.model_validate(payload)

    def _filter_versions(
        self,
        versions: Iterable[ConfigVersion],
        include_deleted: bool,
    ) -> list[ConfigVersion]:
        if include_deleted:
            return list(versions)
        return [version for version in versions if version.deleted_at is None]

    async def _get_config_or_error(self, workspace_id: str, config_id: str) -> Config:
        config = await self._repository.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=True,
        )
        if config is None:
            raise ConfigNotFoundError(config_id)
        if config.deleted_at is not None:
            raise ConfigNotFoundError(config_id)
        return config

    def _draft_package_dir(self, config_id: str, draft_id: str) -> Path:
        package_dir = self._storage.draft_package_dir(config_id, draft_id)
        if not package_dir.exists():
            raise ConfigDraftNotFoundError(draft_id)
        return package_dir

    def _load_draft_metadata(
        self,
        *,
        workspace_id: str,
        config_id: str,
        draft_id: str,
    ) -> DraftMetadata:
        try:
            payload = self._storage.read_draft_metadata(config_id, draft_id)
        except FileNotFoundError as exc:
            raise ConfigDraftNotFoundError(draft_id) from exc
        metadata = DraftMetadata.from_json(payload)
        if metadata.config_id != config_id or metadata.workspace_id != workspace_id:
            raise ConfigDraftNotFoundError(draft_id)
        return metadata

    def _save_draft_metadata(self, config_id: str, metadata: DraftMetadata) -> None:
        self._storage.update_draft_metadata(config_id, metadata.draft_id, metadata.to_json())

    def _touch_draft_metadata(
        self,
        *,
        metadata: DraftMetadata,
        actor: str | None,
    ) -> None:
        metadata.updated_at = utc_now()
        metadata.updated_by_user_id = actor

    def _build_draft_record(self, metadata: DraftMetadata) -> ConfigDraftRecord:
        payload = {
            "draft_id": metadata.draft_id,
            "config_id": metadata.config_id,
            "workspace_id": metadata.workspace_id,
            "base_config_version_id": metadata.base_config_version_id,
            "base_sequence": metadata.base_sequence,
            "manifest_sha256": metadata.manifest_sha256,
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
            "created_by_user_id": metadata.created_by_user_id,
            "updated_by_user_id": metadata.updated_by_user_id,
            "last_published_version_id": metadata.last_published_version_id,
        }
        return ConfigDraftRecord.model_validate(payload)

    def _build_package_entry(self, entry: PackageFileMetadata) -> ConfigPackageEntry:
        return ConfigPackageEntry(
            path=entry.path,
            type=entry.type,  # type: ignore[arg-type]
            size=entry.size,
            sha256=entry.sha256,
        )

    def _load_manifest(self, manifest: dict[str, Any], *, context: str) -> ManifestV1:
        try:
            return self._manifest_loader.load(manifest)
        except ManifestError as exc:
            raise InvalidConfigManifestError(f"{context}: {exc}") from exc

    def _canonical_manifest(self, manifest: ManifestV1) -> dict[str, Any]:
        return manifest.model_dump(mode="json")

    def _manifest_for_storage(self, manifest: ManifestV1) -> dict[str, Any]:
        return manifest.model_dump(mode="json", by_alias=True)

    def _ensure_package_manifest_alignment(
        self,
        *,
        archive_bytes: bytes,
        canonical_manifest: dict[str, Any],
    ) -> None:
        try:
            with ZipFile(io.BytesIO(archive_bytes)) as archive:
                with archive.open("manifest.json") as stream:
                    packaged_manifest = json.load(stream)
        except KeyError as exc:
            raise InvalidConfigManifestError("Config package is missing manifest.json") from exc
        except json.JSONDecodeError as exc:
            raise InvalidConfigManifestError("Config package manifest.json is not valid JSON") from exc

        packaged_model = self._load_manifest(
            packaged_manifest,
            context="Manifest embedded in config package failed validation",
        )
        packaged_canonical = self._canonical_manifest(packaged_model)
        if packaged_canonical != canonical_manifest:
            raise InvalidConfigManifestError(
                "Manifest payload does not match manifest.json in the package",
            )

    def _ensure_no_validation_errors(self, diagnostics: Iterable[Diagnostic]) -> None:
        diagnostics_list = list(diagnostics)
        errors = [
            diagnostic
            for diagnostic in diagnostics_list
            if getattr(diagnostic, "level", DiagnosticLevel.ERROR) == DiagnosticLevel.ERROR
        ]
        if errors:
            raise InvalidConfigManifestError(
                "Config package failed validation",
                diagnostics=diagnostics_list,
            )

    def _hash_manifest(self, manifest: dict[str, Any]) -> str:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _hash_text(self, content: str, *, encoding: str) -> str:
        return hashlib.sha256(content.encode(encoding)).hexdigest()

    def _archive_name(self, filename: str, sequence: int) -> str:
        _ = filename  # Original filename intentionally ignored for canonical naming
        return f"v{sequence:04d}.zip"

    def _actor_id(self, actor: User | None) -> str | None:
        return getattr(actor, "id", None)


__all__ = ["ConfigsService"]
