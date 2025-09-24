"""Service layer for configuration queries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...core.service import BaseService, ServiceContext
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
        limit: int,
        offset: int,
        document_type: str | None = None,
    ) -> list[ConfigurationRecord]:
        """Return configurations ordered by recency."""

        configurations = await self._repository.list_configurations(
            limit=limit,
            offset=offset,
            document_type=document_type,
        )
        records = [ConfigurationRecord.model_validate(row) for row in configurations]

        payload: dict[str, Any] = {
            "count": len(records),
            "limit": limit,
            "offset": offset,
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
