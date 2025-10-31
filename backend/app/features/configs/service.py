"""Service orchestration for the file-backed configuration engine."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings, get_settings

from .exceptions import (
    ConfigActivationError,
    ConfigError,
    ConfigExportError,
    ConfigFileNotFoundError,
    ConfigFileOperationError,
    ConfigImportError,
    ConfigNotFoundError,
    ConfigSecretNotFoundError,
    ConfigStatusConflictError,
)
from .files import ConfigFilesystem
from .manifests import load_manifest, save_manifest
from .models import Config, ConfigStatus
from .repository import ConfigsRepository
from .schemas import (
    ConfigRecord,
    ConfigSecretMetadata,
    FileItem,
    Manifest,
    ValidationIssue,
)
from .secrets import encrypt_secret
from .validation import validate_bundle


Initializer = Callable[[str], Awaitable[None] | None]


def _now() -> datetime:
    return datetime.now(tz=UTC)


class ConfigService:
    """High-level operations for managing configuration bundles."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings | None = None,
        filesystem: ConfigFilesystem | None = None,
    ) -> None:
        settings = settings or get_settings()
        configs_dir = settings.storage_configs_dir
        if configs_dir is None:
            raise RuntimeError("Configuration storage directory is not configured")

        self._session = session
        self._settings = settings
        self._filesystem = filesystem or ConfigFilesystem(Path(configs_dir))
        self._repo = ConfigsRepository(session)

    # ------------------------------------------------------------------
    # CRUD & lifecycle
    # ------------------------------------------------------------------
    async def list_configs(
        self,
        *,
        workspace_id: str,
        statuses: Iterable[str] | None = None,
    ) -> list[ConfigRecord]:
        parsed_statuses = self._parse_statuses(statuses)
        configs = await self._repo.list_configs(
            workspace_id=workspace_id, statuses=parsed_statuses
        )
        return [self._serialize_config(config) for config in configs]

    async def get_active_config(
        self, *, workspace_id: str
    ) -> ConfigRecord | None:
        config = await self._repo.get_active_config(workspace_id)
        if config is None:
            return None
        return self._serialize_config(config)

    async def get_config(self, *, workspace_id: str, config_id: str) -> ConfigRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        return self._serialize_config(config)

    async def create_config(
        self,
        *,
        workspace_id: str,
        title: str,
        note: str | None = None,
        from_config_id: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        initializer: Initializer
        if from_config_id:
            await self._get_config_or_error(workspace_id, from_config_id)

            async def initializer(config_id: str) -> None:
                await self._clone_files(
                    workspace_id=workspace_id,
                    source_config_id=from_config_id,
                    destination_config_id=config_id,
                )

        else:

            def initializer(config_id: str) -> None:
                self._seed_from_template(config_id)

        config = await self._create_bundle(
            workspace_id=workspace_id,
            title=title.strip(),
            note=note.strip() if note else None,
            actor_id=actor_id,
            initializer=initializer,
        )
        return self._serialize_config(config)

    async def update_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        title: str | None = None,
        note: str | None = None,
        version: str | None = None,
    ) -> ConfigRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        self._ensure_editable(config)

        if title is not None:
            config.title = title.strip()
        if note is not None:
            config.note = note.strip() or None
        if version is not None:
            config.version = version.strip()

        await self._persist_config(config)
        return self._serialize_config(config)

    async def delete_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> None:
        config = await self._get_config_or_error(workspace_id, config_id)
        if config.status == ConfigStatus.ACTIVE:
            raise ConfigStatusConflictError(
                config.config_id,
                config.status.value,
                "Active configurations cannot be deleted",
            )

        await self._repo.delete_config(config)
        await self._session.flush()
        self._filesystem.delete_config(config.config_id)

    async def archive_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        if config.status == ConfigStatus.ACTIVE:
            raise ConfigStatusConflictError(
                config.config_id,
                config.status.value,
                "Active configurations cannot be archived",
            )
        if config.status == ConfigStatus.ARCHIVED:
            return self._serialize_config(config)

        config.status = ConfigStatus.ARCHIVED
        config.archived_at = _now()
        config.archived_by = actor_id

        await self._persist_config(config)
        return self._serialize_config(config)

    async def unarchive_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> ConfigRecord:
        config = await self._get_config_or_error(workspace_id, config_id)
        if config.status != ConfigStatus.ARCHIVED:
            return self._serialize_config(config)

        config.status = ConfigStatus.INACTIVE
        config.archived_at = None
        config.archived_by = None

        await self._persist_config(config)
        return self._serialize_config(config)

    async def activate_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        config = await self._get_config_or_error(
            workspace_id,
            config_id,
            for_update=True,
        )
        if config.status == ConfigStatus.ARCHIVED:
            raise ConfigStatusConflictError(
                config.config_id,
                config.status.value,
                "Archived configurations cannot be activated",
            )

        await self._repo.deactivate_all(workspace_id)
        config.status = ConfigStatus.ACTIVE
        config.activated_by = actor_id
        config.activated_at = _now()

        try:
            await self._repo.set_workspace_active_config(
                workspace_id=workspace_id, config_id=config.config_id
            )
        except IntegrityError as exc:  # pragma: no cover - defensive guard
            raise ConfigActivationError(
                config.config_id, "Failed to update workspace active pointer"
            ) from exc

        await self._persist_config(config)
        return self._serialize_config(config)

    async def clone_config(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        title: str,
        note: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        await self._get_config_or_error(workspace_id, source_config_id)

        async def initializer(config_id: str) -> None:
            await self._clone_files(
                workspace_id=workspace_id,
                source_config_id=source_config_id,
                destination_config_id=config_id,
            )

        clone = await self._create_bundle(
            workspace_id=workspace_id,
            title=title.strip(),
            note=note.strip() if note else None,
            actor_id=actor_id,
            initializer=initializer,
        )
        return self._serialize_config(clone)

    async def import_config(
        self,
        *,
        workspace_id: str,
        title: str,
        archive_bytes: bytes,
        note: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        def initializer(config_id: str) -> None:
            self._filesystem.import_archive(config_id, archive_bytes)

        try:
            config = await self._create_bundle(
                workspace_id=workspace_id,
                title=title.strip(),
                note=note.strip() if note else None,
                actor_id=actor_id,
                initializer=initializer,
            )
        except Exception as exc:
            raise ConfigImportError(str(exc)) from exc

        return self._serialize_config(config)

    async def export_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> bytes:
        config = await self._get_config_or_error(workspace_id, config_id)

        try:
            return self._filesystem.export_archive(config.config_id)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(config.config_id, "/") from exc
        except OSError as exc:  # pragma: no cover - defensive
            raise ConfigExportError("Failed to export configuration bundle") from exc

    # ------------------------------------------------------------------
    # Manifest & files
    # ------------------------------------------------------------------
    async def get_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> Manifest:
        config = await self._get_config_or_error(workspace_id, config_id)
        return load_manifest(self._filesystem, config.config_id)

    async def put_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
        manifest: Manifest,
    ) -> Manifest:
        config = await self._get_editable_config(workspace_id, config_id)
        payload = manifest.model_copy(deep=True)
        return await self._save_manifest(config, payload)

    async def list_files(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[FileItem]:
        config = await self._get_config_or_error(workspace_id, config_id)
        metadata = self._filesystem.list_files(config.config_id)
        return [
            FileItem(path=item.path, byte_size=item.byte_size, sha256=item.sha256)
            for item in metadata
        ]

    async def read_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
    ) -> str:
        config = await self._get_config_or_error(workspace_id, config_id)
        try:
            return self._filesystem.read_text(config.config_id, path)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(config.config_id, path) from exc

    async def write_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
        content: str,
    ) -> FileItem:
        config = await self._get_editable_config(workspace_id, config_id)
        metadata = self._filesystem.write_text(config.config_id, path, content)
        await self._finalize_bundle_update(config)
        return FileItem(
            path=metadata.path,
            byte_size=metadata.byte_size,
            sha256=metadata.sha256,
        )

    async def delete_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
    ) -> None:
        config = await self._get_editable_config(workspace_id, config_id)
        try:
            self._filesystem.delete_file(config.config_id, path)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(config.config_id, path) from exc

        await self._finalize_bundle_update(config)

    async def rename_column(
        self,
        *,
        workspace_id: str,
        config_id: str,
        from_key: str,
        to_key: str,
    ) -> Manifest:
        config = await self._get_editable_config(workspace_id, config_id)
        manifest = self._load_manifest(config)

        if from_key not in manifest.columns.meta:
            raise ConfigFileOperationError(
                config.config_id,
                from_key,
                f"Column {from_key!r} does not exist in manifest",
            )
        if from_key == to_key:
            return manifest
        if to_key in manifest.columns.meta:
            raise ConfigFileOperationError(
                config.config_id,
                to_key,
                f"Column {to_key!r} already exists",
            )

        script_path = manifest.columns.meta[from_key].script
        script_relative = PurePosixPath(script_path)
        bundle_root = self._filesystem.config_path(config.config_id)
        source_path = self._ensure_within_bundle(
            bundle_root, script_relative, config.config_id, script_path
        )
        if not source_path.exists():
            raise ConfigFileNotFoundError(config.config_id, script_path)

        renamed_relative = script_relative
        renamed_file = False

        if script_relative.suffix == ".py" and script_relative.stem == from_key:
            candidate = script_relative.with_name(f"{to_key}.py")
            destination_path = self._ensure_within_bundle(
                bundle_root, candidate, config.config_id, candidate.as_posix()
            )
            if destination_path.exists():
                raise ConfigFileOperationError(
                    config.config_id,
                    candidate.as_posix(),
                    f"A script already exists at '{candidate.as_posix()}'",
                )
            try:
                self._filesystem.rename_file(
                    config.config_id,
                    script_relative.as_posix(),
                    candidate.as_posix(),
                )
            except FileNotFoundError as exc:
                raise ConfigFileNotFoundError(
                    config.config_id, script_relative.as_posix()
                ) from exc
            renamed_relative = candidate
            renamed_file = True

        def mutate(working: Manifest) -> None:
            column_meta = working.columns.meta.pop(from_key)
            column_meta.script = renamed_relative.as_posix()
            working.columns.meta[to_key] = column_meta
            working.columns.order = [
                to_key if key == from_key else key for key in working.columns.order
            ]

        try:
            return await self._update_manifest(config, mutate, base=manifest)
        except Exception:
            if renamed_file:
                with suppress(Exception):
                    self._filesystem.rename_file(
                        config.config_id,
                        renamed_relative.as_posix(),
                        script_relative.as_posix(),
                    )
            raise

    # ------------------------------------------------------------------
    # Validation helpers & secrets
    # ------------------------------------------------------------------
    async def validate_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> tuple[Manifest | None, list[ValidationIssue]]:
        config = await self._get_config_or_error(workspace_id, config_id)
        bundle_path = self._filesystem.config_path(config.config_id)
        result = validate_bundle(bundle_path)
        return result.manifest, result.issues

    async def list_secrets(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[ConfigSecretMetadata]:
        config = await self._get_config_or_error(workspace_id, config_id)
        manifest = self._load_manifest(config)

        items = [
            ConfigSecretMetadata(
                name=name,
                key_id=cipher.key_id,
                created_at=cipher.created_at,
            )
            for name, cipher in manifest.secrets.items()
        ]
        items.sort(key=lambda item: item.name)
        return items

    async def put_secret(
        self,
        *,
        workspace_id: str,
        config_id: str,
        name: str,
        value: str,
        key_id: str = "default",
    ) -> ConfigSecretMetadata:
        config = await self._get_editable_config(workspace_id, config_id)
        cipher = encrypt_secret(value, settings=self._settings, key_id=key_id)

        manifest = self._load_manifest(config)

        def mutate(working: Manifest) -> None:
            working.secrets[name] = cipher

        saved = await self._update_manifest(config, mutate, base=manifest)
        saved_cipher = saved.secrets[name]
        return ConfigSecretMetadata(
            name=name,
            key_id=saved_cipher.key_id,
            created_at=saved_cipher.created_at,
        )

    async def delete_secret(
        self,
        *,
        workspace_id: str,
        config_id: str,
        name: str,
    ) -> None:
        config = await self._get_editable_config(workspace_id, config_id)

        manifest = self._load_manifest(config)

        def mutate(working: Manifest) -> None:
            if name not in working.secrets:
                raise ConfigSecretNotFoundError(config.config_id, name)
            working.secrets.pop(name)

        await self._update_manifest(config, mutate, base=manifest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _get_config_or_error(
        self,
        workspace_id: str,
        config_id: str,
        *,
        for_update: bool = False,
    ) -> Config:
        config = await self._repo.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            for_update=for_update,
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        return config

    async def _get_editable_config(
        self, workspace_id: str, config_id: str, *, for_update: bool = False
    ) -> Config:
        config = await self._get_config_or_error(
            workspace_id, config_id, for_update=for_update
        )
        self._ensure_editable(config)
        return config

    async def _persist_config(self, config: Config) -> None:
        await self._session.flush()
        await self._session.refresh(config)

    @staticmethod
    def _serialize_config(config: Config) -> ConfigRecord:
        return ConfigRecord.model_validate(config)

    def _ensure_editable(self, config: Config) -> None:
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

    def _refresh_package_hash(self, config: Config) -> None:
        digest = self._filesystem.compute_package_hash(config.config_id)
        config.files_hash = digest or None
        config.package_sha256 = digest or None

    async def _finalize_bundle_update(self, config: Config) -> None:
        self._refresh_package_hash(config)
        await self._persist_config(config)

    def _load_manifest(self, config: Config) -> Manifest:
        return load_manifest(self._filesystem, config.config_id)

    async def _save_manifest(self, config: Config, manifest: Manifest) -> Manifest:
        saved = save_manifest(self._filesystem, config.config_id, manifest)
        await self._finalize_bundle_update(config)
        return saved

    async def _update_manifest(
        self,
        config: Config,
        mutator: Callable[[Manifest], None],
        *,
        base: Manifest | None = None,
    ) -> Manifest:
        manifest = base or self._load_manifest(config)
        working = manifest.model_copy(deep=True)
        mutator(working)
        return await self._save_manifest(config, working)

    def _ensure_within_bundle(
        self,
        bundle_root: Path,
        relative: PurePosixPath,
        config_id: str,
        display_path: str,
    ) -> Path:
        candidate = (bundle_root / Path(*relative.parts)).resolve()
        if not candidate.is_relative_to(bundle_root):
            raise ConfigFileOperationError(
                config_id,
                display_path,
                "Script path escapes configuration directory",
            )
        return candidate

    async def _clone_files(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        destination_config_id: str,
    ) -> None:
        await self._get_config_or_error(workspace_id, source_config_id)
        try:
            self._filesystem.copy_config(source_config_id, destination_config_id)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(source_config_id, "/") from exc

    def _seed_from_template(self, config_id: str) -> None:
        template_dir = (
            Path(__file__).resolve().parent / "templates" / "default_config"
        )
        self._filesystem.copy_template(template_dir, config_id)

    def _parse_statuses(
        self, statuses: Iterable[str] | None
    ) -> tuple[ConfigStatus, ...] | None:
        if statuses is None:
            return (ConfigStatus.ACTIVE, ConfigStatus.INACTIVE)
        normalized: list[ConfigStatus] = []
        for status in statuses:
            text = status.strip().lower()
            if text == "all":
                return tuple(ConfigStatus)
            try:
                normalized.append(ConfigStatus(text))
            except ValueError as exc:
                raise ConfigError(f"Unsupported status filter: {status}") from exc
        return tuple(dict.fromkeys(normalized)) or None

    async def _create_bundle(
        self,
        *,
        workspace_id: str,
        title: str,
        note: str | None,
        actor_id: str | None,
        initializer: Initializer,
    ) -> Config:
        config = await self._repo.create_config(
            workspace_id=workspace_id,
            title=title,
            note=note,
            created_by=actor_id,
        )

        try:
            await self._run_initializer(initializer, config.config_id)
        except Exception:
            await self._repo.delete_config(config)
            await self._session.flush()
            self._filesystem.delete_config(config.config_id)
            raise

        await self._finalize_bundle_update(config)
        return config

    async def _run_initializer(self, initializer: Initializer, config_id: str) -> None:
        result = initializer(config_id)
        if inspect.isawaitable(result):
            await result
__all__ = ["ConfigService"]
