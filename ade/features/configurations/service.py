"""Service layer for configuration queries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import ConfigurationNotFoundError
from .repository import ConfigurationsRepository
from .schemas import ConfigurationRecord


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
    ) -> ConfigurationRecord:
        """Create a configuration with the next sequential version."""

        version = await self._repository.determine_next_version(
            workspace_id=workspace_id,
        )
        configuration = await self._repository.create_configuration(
            workspace_id=workspace_id,
            title=title,
            payload=payload,
            version=version,
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


__all__ = ["ConfigurationsService"]
