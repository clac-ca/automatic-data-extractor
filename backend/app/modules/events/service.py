from __future__ import annotations

from ...core.service import BaseService, ServiceContext
from .repository import EventsRepository
from .schemas import EventRecord

_DOCUMENT_ENTITY = "document"


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

        events = await self._repository.list_events_for_entity(
            entity_type=_DOCUMENT_ENTITY,
            entity_id=document_id,
            limit=limit,
            offset=offset,
        )
        return [EventRecord.model_validate(event) for event in events]


__all__ = ["EventsService"]
