"""Service layer for configuration queries."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import (
    ActiveConfigurationNotFoundError,
    ConfigurationColumnNotFoundError,
    ConfigurationColumnValidationError,
    ConfigurationNotFoundError,
    ConfigurationScriptValidationError,
    ConfigurationScriptVersionNotFoundError,
    ConfigurationScriptVersionOwnershipError,
)
from .models import ConfigurationColumn, ConfigurationScriptVersion
from .repository import ConfigurationsRepository
from .schemas import (
    ConfigurationColumnBindingUpdate,
    ConfigurationColumnIn,
    ConfigurationColumnOut,
    ConfigurationRecord,
    ConfigurationScriptVersionIn,
    ConfigurationScriptVersionOut,
)
from .validation import validate_configuration_script


class ConfigurationsService:
    """Expose read-only helpers for configuration metadata."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repository = ConfigurationsRepository(session)

    async def list_configurations(
        self,
        *,
        workspace_id: str,
        is_active: bool | None = None,
    ) -> list[ConfigurationRecord]:
        """Return configurations ordered by recency."""

        configurations = await self._repository.list_configurations(
            workspace_id=workspace_id,
            is_active=is_active,
        )
        records = [ConfigurationRecord.model_validate(row) for row in configurations]

        return records

    async def get_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> ConfigurationRecord:
        """Return a single configuration by identifier."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        return ConfigurationRecord.model_validate(configuration)

    async def create_configuration(
        self,
        *,
        workspace_id: str,
        title: str,
        payload: Mapping[str, Any],
        clone_from_configuration_id: str | None = None,
        clone_from_active: bool = False,
    ) -> ConfigurationRecord:
        """Create a configuration with the next sequential version."""

        version = await self._repository.determine_next_version(
            workspace_id=workspace_id,
        )
        clone_source = None
        if clone_from_configuration_id:
            clone_source = await self._repository.get_configuration(
                clone_from_configuration_id,
                workspace_id=workspace_id,
            )
            if clone_source is None:
                raise ConfigurationNotFoundError(clone_from_configuration_id)
        elif clone_from_active:
            clone_source = await self._repository.get_active_configuration(
                workspace_id=workspace_id,
            )
            if clone_source is None:
                raise ActiveConfigurationNotFoundError(workspace_id)
        if clone_source is not None:
            payload = clone_source.payload

        configuration = await self._repository.create_configuration(
            workspace_id=workspace_id,
            title=title,
            payload=payload,
            version=version,
        )
        if clone_source is not None:
            await self._clone_columns_and_scripts(
                source_configuration_id=str(clone_source.id),
                target_configuration_id=str(configuration.id),
            )
        return ConfigurationRecord.model_validate(configuration)

    async def update_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        title: str,
        payload: Mapping[str, Any],
    ) -> ConfigurationRecord:
        """Replace mutable fields on ``configuration_id``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        updated = await self._repository.update_configuration(
            configuration,
            title=title,
            payload=payload,
        )
        return ConfigurationRecord.model_validate(updated)

    async def delete_configuration(self, *, workspace_id: str, configuration_id: str) -> None:
        """Remove a configuration permanently."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        await self._repository.delete_configuration(configuration)

    async def activate_configuration(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> ConfigurationRecord:
        """Activate ``configuration_id`` and deactivate competing versions."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        activated = await self._repository.activate_configuration(configuration)
        return ConfigurationRecord.model_validate(activated)

    async def list_active_configurations(
        self,
        *,
        workspace_id: str,
    ) -> list[ConfigurationRecord]:
        """Return currently active configurations for the workspace."""

        configurations = await self._repository.list_active_configurations(
            workspace_id=workspace_id,
        )
        return [ConfigurationRecord.model_validate(row) for row in configurations]

    async def list_columns(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> list[ConfigurationColumnOut]:
        """Return ordered columns for ``configuration_id``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        columns = await self._repository.list_columns(
            configuration_id=str(configuration.id),
        )
        return [self._serialize_column(column) for column in columns]

    async def replace_columns(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        columns: Iterable[ConfigurationColumnIn],
    ) -> list[ConfigurationColumnOut]:
        """Replace columns for ``configuration_id`` with ``columns``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        prepared, script_versions = await self._prepare_column_definitions(
            columns=columns,
        )
        if script_versions:
            scripts = await self._validate_column_script_versions(
                configuration_id=str(configuration.id),
                script_version_ids=script_versions,
            )
            for column in prepared:
                script_id = column.get("script_version_id")
                if script_id:
                    script = scripts[script_id]
                    if script.canonical_key != column["canonical_key"]:
                        errors = defaultdict(list)
                        errors["script_version_id"].append(
                            "Script version canonical key mismatch"
                        )
                        raise ConfigurationColumnValidationError(dict(errors))

        stored = await self._repository.replace_columns(
            configuration_id=str(configuration.id),
            definitions=prepared,
        )
        return [self._serialize_column(column) for column in stored]

    async def update_column_binding(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        canonical_key: str,
        binding: ConfigurationColumnBindingUpdate,
    ) -> ConfigurationColumnOut:
        """Update binding metadata for ``canonical_key``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        column = await self._repository.get_column(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
        )
        if column is None:
            raise ConfigurationColumnNotFoundError(configuration_id, canonical_key)

        payload = binding.model_dump(exclude_unset=True)
        script_version_id = payload.get("script_version_id", column.script_version_id)
        if "script_version_id" in payload:
            if script_version_id is not None:
                script = await self._repository.get_script_version_by_id(script_version_id)
                if script is None:
                    raise ConfigurationScriptVersionNotFoundError(script_version_id)
                if script.configuration_id != column.configuration_id:
                    raise ConfigurationScriptVersionOwnershipError(
                        script_version_id, str(configuration.id)
                    )
                if script.canonical_key != canonical_key:
                    errors = defaultdict(list)
                    errors["script_version_id"].append(
                        "Script version canonical key mismatch"
                    )
                    raise ConfigurationColumnValidationError(dict(errors))
            else:
                script = None
        else:
            script = (
                await self._repository.get_script_version_by_id(column.script_version_id)
                if column.script_version_id
                else None
            )

        params = payload.get("params")
        if "params" in payload and params is None:
            params = {}

        updated = await self._repository.update_column(
            column,
            script_version_id=script_version_id,
            params=params,
            enabled=payload.get("enabled"),
            required=payload.get("required"),
        )
        return self._serialize_column(updated, script=script)

    async def create_script_version(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        canonical_key: str,
        payload: ConfigurationScriptVersionIn,
        actor_id: str | None,
    ) -> tuple[ConfigurationScriptVersionOut, str]:
        """Create and validate a configuration script version."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        errors: dict[str, list[str]] = {}
        if payload.canonical_key != canonical_key:
            errors.setdefault("canonical_key", []).append(
                "Body canonical_key must match the path parameter."
            )
        if payload.language.lower() != "python":
            errors.setdefault("language", []).append("Only 'python' scripts are supported.")
        if errors:
            raise ConfigurationScriptValidationError(errors)

        code = payload.code
        sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        outcome = validate_configuration_script(
            code=code,
            canonical_key=canonical_key,
        )
        version = await self._repository.determine_next_script_version(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
        )
        script = await self._repository.create_script_version(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
            version=version,
            language=payload.language,
            code=code,
            code_sha256=sha,
            doc_name=outcome.doc_name,
            doc_description=outcome.doc_description,
            doc_version=outcome.doc_version,
            validated_at=outcome.validated_at,
            validation_errors=outcome.errors,
            created_by_user_id=actor_id,
        )
        return self._serialize_script(script, include_code=False), sha

    async def list_script_versions(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        canonical_key: str,
    ) -> list[ConfigurationScriptVersionOut]:
        """Return script versions for ``canonical_key``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        scripts = await self._repository.list_script_versions(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
        )
        return [self._serialize_script(script, include_code=False) for script in scripts]

    async def get_script_version(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        canonical_key: str,
        script_version_id: str,
        include_code: bool = False,
    ) -> ConfigurationScriptVersionOut:
        """Return metadata for ``script_version_id``."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        script = await self._repository.get_script_version(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
            script_version_id=script_version_id,
        )
        if script is None:
            raise ConfigurationScriptVersionNotFoundError(script_version_id)
        return self._serialize_script(script, include_code=include_code)

    async def validate_script_version(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        canonical_key: str,
        script_version_id: str,
        if_match: str | None,
    ) -> tuple[ConfigurationScriptVersionOut, str]:
        """Re-run validation for ``script_version_id`` returning fresh metadata."""

        configuration = await self._repository.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        script = await self._repository.get_script_version(
            configuration_id=str(configuration.id),
            canonical_key=canonical_key,
            script_version_id=script_version_id,
        )
        if script is None:
            raise ConfigurationScriptVersionNotFoundError(script_version_id)

        if if_match:
            expected = {script.code_sha256, f'W/"{script.code_sha256}"'}
            if if_match not in expected:
                errors = {
                    "if-match": [
                        "ETag mismatch; provide If-Match header for the current script sha256.",
                    ]
                }
                raise ConfigurationScriptValidationError(errors)

        outcome = validate_configuration_script(
            code=script.code,
            canonical_key=canonical_key,
        )
        script = await self._repository.update_script_validation(
            script,
            doc_name=outcome.doc_name,
            doc_description=outcome.doc_description,
            doc_version=outcome.doc_version,
            validated_at=outcome.validated_at,
            validation_errors=outcome.errors,
        )
        return self._serialize_script(script, include_code=False), script.code_sha256

    async def _clone_columns_and_scripts(
        self,
        *,
        source_configuration_id: str,
        target_configuration_id: str,
    ) -> None:
        """Clone columns and scripts from source to target configuration."""

        mapping = await self._repository.clone_script_versions(
            source_configuration_id=source_configuration_id,
            target_configuration_id=target_configuration_id,
        )
        source_columns = await self._repository.list_columns(
            configuration_id=source_configuration_id,
        )
        definitions: list[dict[str, Any]] = []
        for column in source_columns:
            script_id = str(column.script_version_id) if column.script_version_id else None
            definitions.append(
                {
                    "canonical_key": column.canonical_key,
                    "ordinal": column.ordinal,
                    "display_label": column.display_label,
                    "header_color": column.header_color,
                    "width": column.width,
                    "required": column.required,
                    "enabled": column.enabled,
                    "script_version_id": mapping.get(script_id),
                    "params": dict(column.params or {}),
                }
            )
        if definitions:
            await self._repository.replace_columns(
                configuration_id=target_configuration_id,
                definitions=definitions,
            )

    async def _prepare_column_definitions(
        self,
        *,
        columns: Iterable[ConfigurationColumnIn],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        errors: dict[str, list[str]] = defaultdict(list)
        prepared: list[dict[str, Any]] = []
        canonical_counter: Counter[str] = Counter()
        ordinal_counter: Counter[int] = Counter()
        script_version_ids: set[str] = set()

        for column in columns:
            canonical_counter[column.canonical_key] += 1
            ordinal_counter[column.ordinal] += 1
            if column.script_version_id:
                script_version_ids.add(column.script_version_id)

            payload = column.model_dump(exclude_unset=False)
            payload["params"] = dict(column.params or {})
            prepared.append(payload)

        duplicates = [key for key, count in canonical_counter.items() if count > 1]
        if duplicates:
            errors["canonical_key"].append(
                "Canonical keys must be unique per configuration."
            )
        ordinal_duplicates = [key for key, count in ordinal_counter.items() if count > 1]
        if ordinal_duplicates:
            errors["ordinal"].append("Ordinals must be unique per configuration.")

        if errors:
            raise ConfigurationColumnValidationError(dict(errors))

        prepared.sort(key=lambda column: column["ordinal"])
        return prepared, script_version_ids

    async def _validate_column_script_versions(
        self,
        *,
        configuration_id: str,
        script_version_ids: set[str],
    ) -> dict[str, ConfigurationScriptVersion]:
        scripts: dict[str, ConfigurationScriptVersion] = {}
        for identifier in script_version_ids:
            script = await self._repository.get_script_version_by_id(identifier)
            if script is None:
                raise ConfigurationScriptVersionNotFoundError(identifier)
            if script.configuration_id != configuration_id:
                raise ConfigurationScriptVersionOwnershipError(identifier, configuration_id)
            scripts[identifier] = script
        return scripts

    def _serialize_column(
        self,
        column: ConfigurationColumn,
        *,
        script: ConfigurationScriptVersion | None = None,
    ) -> ConfigurationColumnOut:
        schema = ConfigurationColumnOut.model_validate(column)
        if script is None:
            script = column.script_version
        if script is not None:
            schema = schema.model_copy(
                update={
                    "script_version": self._serialize_script(
                        script,
                        include_code=False,
                    )
                }
            )
        return schema

    def _serialize_script(
        self,
        script: ConfigurationScriptVersion,
        *,
        include_code: bool,
    ) -> ConfigurationScriptVersionOut:
        schema = ConfigurationScriptVersionOut.model_validate(script)
        if not include_code:
            schema = schema.model_copy(update={"code": None})
        return schema


__all__ = ["ConfigurationsService"]
