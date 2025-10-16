"""Persistence helpers for configuration queries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Configuration, ConfigurationColumn, ConfigurationScriptVersion


class ConfigurationsRepository:
    """Query helper responsible for configuration lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_configuration(
        self, configuration_id: str, *, workspace_id: str
    ) -> Configuration | None:
        """Return the configuration scoped to ``workspace_id`` when found."""

        return await self.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )

    async def list_configurations(
        self,
        *,
        workspace_id: str,
        is_active: bool | None = None,
    ) -> list[Configuration]:
        """Return configurations ordered by recency."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(Configuration.workspace_id == workspace_id)
            .order_by(
                Configuration.created_at.desc(),
                Configuration.id.desc(),
            )
        )
        if is_active is not None:
            stmt = stmt.where(Configuration.is_active.is_(is_active))

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_configuration(
        self, configuration_id: str, *, workspace_id: str
    ) -> Configuration | None:
        """Return the configuration identified by ``configuration_id`` when available."""

        stmt: Select[tuple[Configuration]] = select(Configuration).where(
            Configuration.id == configuration_id,
            Configuration.workspace_id == workspace_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_active_configuration(
        self,
        *,
        workspace_id: str,
    ) -> Configuration | None:
        """Return the active configuration for ``workspace_id`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_active_configurations(
        self,
        *,
        workspace_id: str,
    ) -> list[Configuration]:
        """Return active configurations scoped by ``workspace_id``."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.is_active.is_(True),
            )
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def determine_next_version(
        self, *, workspace_id: str
    ) -> int:
        """Return the next sequential version for ``workspace_id``."""

        stmt = select(Configuration.version).where(
            Configuration.workspace_id == workspace_id,
        )
        stmt = stmt.order_by(Configuration.version.desc()).limit(1)
        result = await self._session.execute(stmt)
        latest = result.scalars().first()
        return (latest or 0) + 1

    async def create_configuration(
        self,
        *,
        workspace_id: str,
        title: str,
        payload: Mapping[str, Any],
        version: int,
    ) -> Configuration:
        """Persist a configuration record."""

        configuration = Configuration(
            workspace_id=workspace_id,
            title=title,
            version=version,
            is_active=False,
            activated_at=None,
            payload=dict(payload),
        )
        self._session.add(configuration)
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def update_configuration(
        self,
        configuration: Configuration,
        *,
        title: str,
        payload: Mapping[str, Any],
    ) -> Configuration:
        """Update ``configuration`` with the provided fields."""

        configuration.title = title
        configuration.payload = dict(payload)
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def delete_configuration(self, configuration: Configuration) -> None:
        """Remove ``configuration`` from the database."""

        await self._session.delete(configuration)
        await self._session.flush()

    async def activate_configuration(
        self, configuration: Configuration
    ) -> Configuration:
        """Mark ``configuration`` as active and deactivate others for the workspace."""

        await self._session.execute(
            update(Configuration)
            .where(
                Configuration.workspace_id == configuration.workspace_id,
                Configuration.id != configuration.id,
            )
            .values(is_active=False, activated_at=None)
        )

        configuration.is_active = True
        configuration.activated_at = datetime.now(tz=UTC).replace(microsecond=0)
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def get_configuration_by_version(
        self,
        *,
        workspace_id: str,
        version: int,
    ) -> Configuration | None:
        """Return the configuration for ``workspace_id`` at ``version`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_columns(
        self,
        *,
        configuration_id: str,
    ) -> list[ConfigurationColumn]:
        """Return ordered columns for ``configuration_id``."""

        stmt: Select[tuple[ConfigurationColumn]] = (
            select(ConfigurationColumn)
            .where(ConfigurationColumn.configuration_id == configuration_id)
            .options(selectinload(ConfigurationColumn.script_version))
            .order_by(ConfigurationColumn.ordinal.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_column(
        self,
        *,
        configuration_id: str,
        canonical_key: str,
    ) -> ConfigurationColumn | None:
        """Return the column identified by ``canonical_key`` when present."""

        stmt: Select[tuple[ConfigurationColumn]] = (
            select(ConfigurationColumn)
            .where(
                ConfigurationColumn.configuration_id == configuration_id,
                ConfigurationColumn.canonical_key == canonical_key,
            )
            .options(selectinload(ConfigurationColumn.script_version))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def replace_columns(
        self,
        *,
        configuration_id: str,
        definitions: Iterable[dict[str, Any]],
    ) -> list[ConfigurationColumn]:
        """Replace existing columns with ``definitions`` preserving order."""

        await self._session.execute(
            delete(ConfigurationColumn).where(
                ConfigurationColumn.configuration_id == configuration_id
            )
        )
        for payload in definitions:
            column = ConfigurationColumn(
                configuration_id=configuration_id,
                **payload,
            )
            self._session.add(column)
        await self._session.flush()
        return await self.list_columns(configuration_id=configuration_id)

    async def update_column(
        self,
        column: ConfigurationColumn,
        *,
        script_version_id: str | None,
        params: Mapping[str, Any] | None,
        enabled: bool | None,
        required: bool | None,
    ) -> ConfigurationColumn:
        """Update binding metadata on ``column``."""

        column.script_version_id = script_version_id
        if params is not None:
            column.params = dict(params)
        if enabled is not None:
            column.enabled = enabled
        if required is not None:
            column.required = required
        await self._session.flush()
        await self._session.refresh(column)
        return column

    async def determine_next_script_version(
        self,
        *,
        configuration_id: str,
        canonical_key: str,
    ) -> int:
        """Return the next version for a script within ``configuration_id``."""

        stmt = (
            select(func.max(ConfigurationScriptVersion.version))
            .where(
                ConfigurationScriptVersion.configuration_id == configuration_id,
                ConfigurationScriptVersion.canonical_key == canonical_key,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        latest = result.scalar_one_or_none() or 0
        return latest + 1

    async def create_script_version(
        self,
        *,
        configuration_id: str,
        canonical_key: str,
        version: int,
        language: str,
        code: str,
        code_sha256: str,
        doc_name: str | None,
        doc_description: str | None,
        doc_version: int | None,
        validated_at: datetime | None,
        validation_errors: dict[str, list[str]] | None,
        created_by_user_id: str | None,
    ) -> ConfigurationScriptVersion:
        """Persist a script version payload."""

        script = ConfigurationScriptVersion(
            configuration_id=configuration_id,
            canonical_key=canonical_key,
            version=version,
            language=language,
            code=code,
            code_sha256=code_sha256,
            doc_name=doc_name or canonical_key,
            doc_description=doc_description,
            doc_declared_version=doc_version,
            validated_at=validated_at,
            validation_errors=validation_errors,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(script)
        await self._session.flush()
        await self._session.refresh(script)
        return script

    async def list_script_versions(
        self,
        *,
        configuration_id: str,
        canonical_key: str,
    ) -> list[ConfigurationScriptVersion]:
        """Return script versions ordered by recency for ``canonical_key``."""

        stmt: Select[tuple[ConfigurationScriptVersion]] = (
            select(ConfigurationScriptVersion)
            .where(
                ConfigurationScriptVersion.configuration_id == configuration_id,
                ConfigurationScriptVersion.canonical_key == canonical_key,
            )
            .order_by(ConfigurationScriptVersion.version.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_script_version(
        self,
        *,
        configuration_id: str,
        canonical_key: str,
        script_version_id: str,
    ) -> ConfigurationScriptVersion | None:
        """Return a single script version when available."""

        stmt: Select[tuple[ConfigurationScriptVersion]] = (
            select(ConfigurationScriptVersion)
            .where(
                ConfigurationScriptVersion.configuration_id == configuration_id,
                ConfigurationScriptVersion.canonical_key == canonical_key,
                ConfigurationScriptVersion.id == script_version_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_script_version_by_id(
        self, script_version_id: str
    ) -> ConfigurationScriptVersion | None:
        """Return a script version by primary key."""

        return await self._session.get(ConfigurationScriptVersion, script_version_id)

    async def update_script_validation(
        self,
        script: ConfigurationScriptVersion,
        *,
        doc_name: str | None,
        doc_description: str | None,
        doc_version: int | None,
        validated_at: datetime | None,
        validation_errors: dict[str, list[str]] | None,
    ) -> ConfigurationScriptVersion:
        """Update validation metadata for ``script``."""

        if doc_name:
            script.doc_name = doc_name
        script.doc_description = doc_description
        script.doc_declared_version = doc_version
        script.validated_at = validated_at
        script.validation_errors = validation_errors
        await self._session.flush()
        await self._session.refresh(script)
        return script

    async def clone_script_versions(
        self,
        *,
        source_configuration_id: str,
        target_configuration_id: str,
    ) -> dict[str, str]:
        """Clone script versions returning mapping of source→target identifiers."""

        stmt = select(ConfigurationScriptVersion).where(
            ConfigurationScriptVersion.configuration_id == source_configuration_id
        )
        result = await self._session.execute(stmt)
        clones: dict[str, str] = {}
        for source in result.scalars().all():
            script = ConfigurationScriptVersion(
                configuration_id=target_configuration_id,
                canonical_key=source.canonical_key,
                version=source.version,
                language=source.language,
                code=source.code,
                code_sha256=source.code_sha256,
                doc_name=source.doc_name,
                doc_description=source.doc_description,
                doc_declared_version=source.doc_declared_version,
                validated_at=source.validated_at,
                validation_errors=source.validation_errors,
                created_by_user_id=source.created_by_user_id,
            )
            self._session.add(script)
            await self._session.flush()
            clones[str(source.id)] = str(script.id)
        return clones


__all__ = ["ConfigurationsRepository"]
