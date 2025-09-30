"""Service layer for configuration queries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.service import BaseService, ServiceContext
from ..events.recorder import persist_event
from .exceptions import ConfigurationNotFoundError
from .repository import ConfigurationsRepository
from .schemas import ConfigurationRecord


class ConfigurationsService(BaseService):
    """Expose read-only helpers for configuration metadata."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("ConfigurationsService requires a database session")
        self._repository = ConfigurationsRepository(self.session)

    async def list_configurations(
        self,
        *,
        document_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[ConfigurationRecord]:
        """Return configurations ordered by recency."""

        configurations = await self._repository.list_configurations(
            document_type=document_type,
            is_active=is_active,
        )
        records = [ConfigurationRecord.model_validate(row) for row in configurations]

        payload: dict[str, Any] = {
            "count": len(records),
        }
        if document_type:
            payload["document_type"] = document_type
        if is_active is not None:
            payload["is_active"] = is_active

        metadata: dict[str, Any] = {"entity_type": "configuration_collection"}
        workspace = self.current_workspace
        workspace_id = None
        if workspace is not None:
            workspace_id = getattr(workspace, "workspace_id", None) or getattr(
                workspace, "id", None
            )
        metadata["entity_id"] = str(workspace_id) if workspace_id is not None else "global"

        await self.publish_event("configurations.listed", payload, metadata=metadata)
        return records

    async def get_configuration(
        self,
        *,
        configuration_id: str,
        emit_event: bool = True,
    ) -> ConfigurationRecord:
        """Return a single configuration by identifier."""

        configuration = await self._repository.get_configuration(configuration_id)
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        record = ConfigurationRecord.model_validate(configuration)
        if emit_event:
            metadata = {"entity_type": "configuration", "entity_id": record.configuration_id}
            payload = {
                "configuration_id": record.configuration_id,
                "document_type": record.document_type,
                "version": record.version,
            }
            await self.publish_event(
                "configuration.viewed",
                payload,
                metadata=metadata,
            )
        return record

    async def create_configuration(
        self,
        *,
        document_type: str,
        title: str,
        payload: Mapping[str, Any],
    ) -> ConfigurationRecord:
        """Create a configuration with the next sequential version."""

        version = await self._repository.determine_next_version(document_type)
        configuration = await self._repository.create_configuration(
            document_type=document_type,
            title=title,
            payload=payload,
            version=version,
        )
        record = ConfigurationRecord.model_validate(configuration)

        event_payload = {
            "configuration_id": record.configuration_id,
            "document_type": record.document_type,
            "version": record.version,
        }
        metadata = {"entity_type": "configuration", "entity_id": record.configuration_id}
        await self.publish_event("configuration.created", event_payload, metadata=metadata)
        return record

    async def update_configuration(
        self,
        *,
        configuration_id: str,
        title: str,
        payload: Mapping[str, Any],
    ) -> ConfigurationRecord:
        """Replace mutable fields on ``configuration_id``."""

        configuration = await self._repository.get_configuration(configuration_id)
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        updated = await self._repository.update_configuration(
            configuration,
            title=title,
            payload=payload,
        )
        record = ConfigurationRecord.model_validate(updated)

        event_payload = {
            "configuration_id": record.configuration_id,
            "document_type": record.document_type,
            "version": record.version,
        }
        metadata = {"entity_type": "configuration", "entity_id": record.configuration_id}
        await self.publish_event("configuration.updated", event_payload, metadata=metadata)
        return record

    async def delete_configuration(self, *, configuration_id: str) -> None:
        """Remove a configuration permanently."""

        configuration = await self._repository.get_configuration(configuration_id)
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        await self._repository.delete_configuration(configuration)

        payload = {
            "configuration_id": configuration_id,
            "document_type": configuration.document_type,
        }
        metadata = {"entity_type": "configuration", "entity_id": configuration_id}
        await self.publish_event("configuration.deleted", payload, metadata=metadata)

    async def activate_configuration(
        self,
        *,
        configuration_id: str,
    ) -> ConfigurationRecord:
        """Activate ``configuration_id`` and deactivate competing versions."""

        configuration = await self._repository.get_configuration(configuration_id)
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)

        activated = await self._repository.activate_configuration(configuration)
        record = ConfigurationRecord.model_validate(activated)

        payload = {
            "configuration_id": record.configuration_id,
            "document_type": record.document_type,
            "activated_at": record.activated_at,
        }
        metadata = {"entity_type": "configuration", "entity_id": record.configuration_id}
        await self.publish_event("configuration.activated", payload, metadata=metadata)
        return record

    async def list_active_configurations(
        self, *, document_type: str | None = None
    ) -> list[ConfigurationRecord]:
        """Return currently active configurations grouped by document type."""

        configurations = await self._repository.list_active_configurations(document_type)
        records = [ConfigurationRecord.model_validate(row) for row in configurations]

        payload: dict[str, Any] = {
            "count": len(records),
        }
        if document_type:
            payload["document_type"] = document_type

        metadata: dict[str, Any] = {"entity_type": "configuration_collection"}
        workspace = self.current_workspace
        workspace_id = None
        if workspace is not None:
            workspace_id = getattr(workspace, "workspace_id", None) or getattr(
                workspace, "id", None
            )
        metadata["entity_id"] = str(workspace_id) if workspace_id is not None else "global"

        await self.publish_event(
            "configurations.list_active", payload, metadata=metadata
        )
        return records

    async def _persist_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        if self.session is None:
            return

        await persist_event(
            self.session,
            name=name,
            payload=payload,
            metadata=metadata,
            correlation_id=self.correlation_id,
        )


__all__ = ["ConfigurationsService"]
