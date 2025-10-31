"""Service orchestration for the file-backed configuration engine."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings, get_settings
from pydantic import ValidationError

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
    ManifestInvalidError,
    PlaintextSecretRejectedError,
)
from .files import ConfigFilesystem
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
        return [ConfigRecord.model_validate(config) for config in configs]

    async def get_active_config(
        self, *, workspace_id: str
    ) -> ConfigRecord | None:
        config = await self._repo.get_active_config(workspace_id)
        if config is None:
            return None
        return ConfigRecord.model_validate(config)

    async def get_config(self, *, workspace_id: str, config_id: str) -> ConfigRecord:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        return ConfigRecord.model_validate(config)

    async def create_config(
        self,
        *,
        workspace_id: str,
        title: str,
        note: str | None = None,
        from_config_id: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        config = await self._repo.create_config(
            workspace_id=workspace_id,
            title=title.strip(),
            note=note.strip() if note else None,
            created_by=actor_id,
        )

        try:
            if from_config_id:
                await self._clone_files(
                    workspace_id=workspace_id,
                    source_config_id=from_config_id,
                    destination_config_id=config.config_id,
                )
            else:
                self._seed_from_template(config.config_id)
        except Exception:
            await self._repo.delete_config(config)
            await self._session.flush()
            self._filesystem.delete_config(config.config_id)
            raise

        await self._refresh_hash_metadata(config)
        return ConfigRecord.model_validate(config)

    async def update_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        title: str | None = None,
        note: str | None = None,
        version: str | None = None,
    ) -> ConfigRecord:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

        if title is not None:
            config.title = title.strip()
        if note is not None:
            config.note = note.strip() or None
        if version is not None:
            config.version = version.strip()

        await self._session.flush()
        await self._session.refresh(config)
        return ConfigRecord.model_validate(config)

    async def delete_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> None:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
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
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status == ConfigStatus.ACTIVE:
            raise ConfigStatusConflictError(
                config.config_id,
                config.status.value,
                "Active configurations cannot be archived",
            )
        if config.status == ConfigStatus.ARCHIVED:
            return ConfigRecord.model_validate(config)

        config.status = ConfigStatus.ARCHIVED
        config.archived_at = _now()
        config.archived_by = actor_id

        await self._session.flush()
        await self._session.refresh(config)
        return ConfigRecord.model_validate(config)

    async def unarchive_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> ConfigRecord:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.ARCHIVED:
            return ConfigRecord.model_validate(config)

        config.status = ConfigStatus.INACTIVE
        config.archived_at = None
        config.archived_by = None

        await self._session.flush()
        await self._session.refresh(config)
        return ConfigRecord.model_validate(config)

    async def activate_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        config = await self._repo.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            for_update=True,
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
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

        await self._session.flush()
        await self._session.refresh(config)
        return ConfigRecord.model_validate(config)

    async def clone_config(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        title: str,
        note: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        source = await self._repo.get_config(
            workspace_id=workspace_id, config_id=source_config_id
        )
        if source is None:
            raise ConfigNotFoundError(workspace_id, source_config_id)

        clone = await self._repo.create_config(
            workspace_id=workspace_id,
            title=title.strip(),
            note=note.strip() if note else None,
            created_by=actor_id,
        )

        try:
            self._filesystem.copy_config(source_config_id, clone.config_id)
        except Exception:
            await self._repo.delete_config(clone)
            await self._session.flush()
            self._filesystem.delete_config(clone.config_id)
            raise

        await self._refresh_hash_metadata(clone)
        return ConfigRecord.model_validate(clone)

    async def import_config(
        self,
        *,
        workspace_id: str,
        title: str,
        archive_bytes: bytes,
        note: str | None = None,
        actor_id: str | None = None,
    ) -> ConfigRecord:
        config = await self._repo.create_config(
            workspace_id=workspace_id,
            title=title.strip(),
            note=note.strip() if note else None,
            created_by=actor_id,
        )

        try:
            self._import_archive(config.config_id, archive_bytes)
        except Exception as exc:
            await self._repo.delete_config(config)
            await self._session.flush()
            self._filesystem.delete_config(config.config_id)
            raise ConfigImportError(str(exc)) from exc

        await self._refresh_hash_metadata(config)
        return ConfigRecord.model_validate(config)

    async def export_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> bytes:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)

        bundle_path = self._filesystem.config_path(config.config_id)
        if not bundle_path.exists():
            raise ConfigFileNotFoundError(config.config_id, "/")

        buffer = io.BytesIO()
        try:
            self._write_zip_from_directory(config.config_id, buffer)
        except Exception as exc:  # pragma: no cover - defensive
            raise ConfigExportError("Failed to export configuration bundle") from exc
        buffer.seek(0)
        return buffer.read()

    # ------------------------------------------------------------------
    # Manifest & files
    # ------------------------------------------------------------------
    async def get_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> Manifest:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)

        try:
            payload = self._filesystem.read_text(config.config_id, "manifest.json")
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(config.config_id, "manifest.json") from exc

        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ManifestInvalidError(
                config.config_id,
                f"manifest.json is not valid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})",
            ) from exc

        try:
            return Manifest.model_validate(raw)
        except ValidationError as exc:
            raise ManifestInvalidError(
                config.config_id,
                "manifest.json does not conform to the v0.5 schema",
            ) from exc

    async def put_manifest(
        self,
        *,
        workspace_id: str,
        config_id: str,
        manifest: Manifest,
    ) -> Manifest:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

        self._ensure_no_plaintext_secrets(config.config_id, manifest)
        payload = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        if not payload.endswith("\n"):
            payload += "\n"

        self._filesystem.write_text(config.config_id, "manifest.json", payload)
        await self._refresh_hash_metadata(config)
        return manifest

    async def list_files(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[FileItem]:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)

        metadata = self._filesystem.list_files(config.config_id)
        return [
            FileItem.model_validate(
                {"path": item.path, "byte_size": item.byte_size, "sha256": item.sha256}
            )
            for item in metadata
        ]

    async def read_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
    ) -> str:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
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
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

        metadata = self._filesystem.write_text(config.config_id, path, content)
        await self._refresh_hash_metadata(config)
        return FileItem.model_validate(
            {"path": metadata.path, "byte_size": metadata.byte_size, "sha256": metadata.sha256}
        )

    async def delete_file(
        self,
        *,
        workspace_id: str,
        config_id: str,
        path: str,
    ) -> None:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

        try:
            self._filesystem.delete_file(config.config_id, path)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(config.config_id, path) from exc
        await self._refresh_hash_metadata(config)

    async def rename_column(
        self,
        *,
        workspace_id: str,
        config_id: str,
        from_key: str,
        to_key: str,
    ) -> Manifest:
        manifest = await self.get_manifest(
            workspace_id=workspace_id, config_id=config_id
        )
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)
        if config.status != ConfigStatus.INACTIVE:
            raise ConfigStatusConflictError(config.config_id, config.status.value)

        if from_key not in manifest.columns.meta:
            raise ConfigFileOperationError(
                config.config_id,
                from_key,
                f"Column {from_key!r} does not exist in manifest",
            )
        if to_key in manifest.columns.meta:
            raise ConfigFileOperationError(
                config.config_id,
                to_key,
                f"Column {to_key!r} already exists",
            )

        column = manifest.columns.meta[from_key]
        script_path = Path(column.script)
        new_script_path = column.script
        performed_rename = False
        should_rename_file = script_path.name == f"{from_key}.py"

        if should_rename_file:
            target_path = script_path.with_name(f"{to_key}.py").as_posix()
            try:
                self._filesystem.rename_file(
                    config.config_id,
                    script_path.as_posix(),
                    target_path,
                )
            except FileNotFoundError as exc:
                raise ConfigFileNotFoundError(
                    config.config_id, script_path.as_posix()
                ) from exc
            except OSError as exc:  # pragma: no cover - filesystem race
                raise ConfigFileOperationError(
                    config.config_id,
                    script_path.as_posix(),
                    f"Failed to rename column script: {exc}",
                ) from exc
            else:
                new_script_path = target_path
                performed_rename = True

        manifest_payload = manifest.model_dump(mode="json")
        order = [to_key if key == from_key else key for key in manifest.columns.order]
        manifest_payload["columns"]["order"] = order

        meta_payload: dict[str, Any] = manifest_payload["columns"]["meta"]
        entry_payload = meta_payload.pop(from_key)
        entry_payload["script"] = new_script_path
        meta_payload[to_key] = entry_payload

        try:
            updated = Manifest.model_validate(manifest_payload)
            await self.put_manifest(
                workspace_id=workspace_id,
                config_id=config_id,
                manifest=updated,
            )
        except Exception:
            if performed_rename:
                try:
                    self._filesystem.rename_file(
                        config.config_id,
                        new_script_path,
                        script_path.as_posix(),
                    )
                except Exception:  # pragma: no cover - best effort rollback
                    pass
            raise

        return await self.get_manifest(workspace_id=workspace_id, config_id=config_id)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    async def validate_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> tuple[Manifest | None, list[ValidationIssue]]:
        config = await self._repo.get_config(
            workspace_id=workspace_id, config_id=config_id
        )
        if config is None:
            raise ConfigNotFoundError(workspace_id, config_id)

        bundle_path = self._filesystem.config_path(config.config_id)
        manifest, issues = validate_bundle(bundle_path)
        return manifest, issues

    async def list_secrets(
        self,
        *,
        workspace_id: str,
        config_id: str,
    ) -> list[ConfigSecretMetadata]:
        manifest = await self.get_manifest(
            workspace_id=workspace_id, config_id=config_id
        )
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
        manifest = await self.get_manifest(
            workspace_id=workspace_id, config_id=config_id
        )
        cipher = encrypt_secret(value, settings=self._settings, key_id=key_id)
        manifest.secrets[name] = cipher
        await self.put_manifest(
            workspace_id=workspace_id,
            config_id=config_id,
            manifest=manifest,
        )
        return ConfigSecretMetadata(
            name=name,
            key_id=cipher.key_id,
            created_at=cipher.created_at,
        )

    async def delete_secret(
        self,
        *,
        workspace_id: str,
        config_id: str,
        name: str,
    ) -> None:
        manifest = await self.get_manifest(
            workspace_id=workspace_id, config_id=config_id
        )
        if name not in manifest.secrets:
            raise ConfigSecretNotFoundError(config_id, name)
        manifest.secrets.pop(name)
        await self.put_manifest(
            workspace_id=workspace_id,
            config_id=config_id,
            manifest=manifest,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _refresh_hash_metadata(self, config: Config) -> None:
        digest = self._filesystem.compute_package_hash(config.config_id)
        config.files_hash = digest or None
        config.package_sha256 = digest or None
        await self._session.flush()
        await self._session.refresh(config)

    async def _clone_files(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        destination_config_id: str,
    ) -> None:
        source = await self._repo.get_config(
            workspace_id=workspace_id, config_id=source_config_id
        )
        if source is None:
            raise ConfigNotFoundError(workspace_id, source_config_id)
        try:
            self._filesystem.copy_config(source.config_id, destination_config_id)
        except FileNotFoundError as exc:
            raise ConfigFileNotFoundError(source.config_id, "/") from exc

    def _seed_from_template(self, config_id: str) -> None:
        template_dir = (
            Path(__file__).resolve().parent / "templates" / "default_config"
        )
        self._filesystem.copy_template(template_dir, config_id)

    def _import_archive(self, config_id: str, archive_bytes: bytes) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
                handle.write(archive_bytes)
                tmp_zip_path = Path(handle.name)
            try:
                shutil.unpack_archive(tmp_zip_path.as_posix(), temp_dir)
            finally:
                try:
                    tmp_zip_path.unlink()
                except FileNotFoundError:  # pragma: no cover - best effort cleanup
                    pass

            source_dir = self._resolve_extracted_root(temp_dir)
            destination = self._filesystem.config_path(config_id)
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_dir, destination, dirs_exist_ok=True)
            self._filesystem.ensure_config_dir(config_id)

    def _write_zip_from_directory(self, config_id: str, buffer: io.BytesIO) -> None:
        import zipfile

        bundle_path = self._filesystem.config_path(config_id)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for metadata in self._filesystem.list_files(config_id):
                file_path = bundle_path / metadata.path
                archive.write(file_path, arcname=metadata.path)

    def _resolve_extracted_root(self, path: Path) -> Path:
        manifest_path = path / "manifest.json"
        if manifest_path.exists():
            return path

        entries = [entry for entry in path.iterdir() if entry.is_dir()]
        if len(entries) == 1:
            candidate = entries[0]
            if (candidate / "manifest.json").exists():
                return candidate
        raise ConfigImportError("Archive does not contain a manifest.json at the root")

    def _ensure_no_plaintext_secrets(self, config_id: str, manifest: Manifest) -> None:
        for name, cipher in manifest.secrets.items():
            if not isinstance(cipher.ciphertext, str):
                raise PlaintextSecretRejectedError(config_id, name)

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


__all__ = ["ConfigService"]
