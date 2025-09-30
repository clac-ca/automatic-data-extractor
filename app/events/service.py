from __future__ import annotations

from app.core.service import BaseService, ServiceContext
from .repository import EventsRepository
from .schemas import EventRecord

_CONFIGURATION_ENTITY = "configuration"
_DOCUMENT_ENTITY = "document"
_JOB_ENTITY = "job"


class EventsService(BaseService):
    """Expose helpers for querying persisted domain events."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("EventsService requires a database session")
        self._repository = EventsRepository(self.session)

    async def list_document_events(
        self,
        *,
        document_id: str,
        limit: int,
        offset: int,
    ) -> list[EventRecord]:
        """Return events associated with ``document_id`` ordered by recency."""

        return await self.list_events(
            entity_type=_DOCUMENT_ENTITY,
            entity_id=document_id,
            limit=limit,
            offset=offset,
        )

    async def list_job_events(
        self,
        *,
        job_id: str,
        limit: int,
        offset: int,
    ) -> list[EventRecord]:
        """Return events associated with ``job_id`` ordered by recency."""

        return await self.list_events(
            entity_type=_JOB_ENTITY,
            entity_id=job_id,
            limit=limit,
            offset=offset,
        )

    async def list_configuration_events(
        self,
        *,
        configuration_id: str,
        limit: int,
        offset: int,
    ) -> list[EventRecord]:
        """Return events associated with ``configuration_id`` ordered by recency."""

        return await self.list_events(
            entity_type=_CONFIGURATION_ENTITY,
            entity_id=configuration_id,
            limit=limit,
            offset=offset,
        )

    async def list_events(
        self,
        *,
        entity_type: str,
        entity_id: str,
        limit: int,
        offset: int,
    ) -> list[EventRecord]:
        """Return events for ``entity_id`` within ``entity_type`` ordered by recency."""

        events = await self._repository.list_events_for_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
        return [EventRecord.model_validate(event) for event in events]


__all__ = ["EventsService"]
