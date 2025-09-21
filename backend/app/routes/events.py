"""Event API endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..services.auth import get_current_user
from ..db import get_db
from ..models import Event
from ..schemas import (
    EventEntitySummary,
    EventListResponse,
    EventResponse,
    ConfigurationTimelineSummary,
    DocumentTimelineSummary,
    JobTimelineSummary,
)
from ..services.events import list_events as list_events_service
from ..services.configurations import (
    ConfigurationNotFoundError,
    get_configuration as get_configuration_service,
)
from ..services.documents import (
    DocumentNotFoundError,
    get_document as get_document_service,
)
from ..services.jobs import JobNotFoundError, get_job as get_job_service

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)


def _to_response(event: Event) -> EventResponse:
    return EventResponse.model_validate(event)


def _load_entity_summary(
    db: Session, entity_type: str, entity_id: str
) -> EventEntitySummary | None:
    if entity_type == "document":
        document = get_document_service(db, entity_id)
        return DocumentTimelineSummary.model_validate(document)
    if entity_type == "configuration":
        configuration = get_configuration_service(db, entity_id)
        return ConfigurationTimelineSummary.model_validate(configuration)
    if entity_type == "job":
        job = get_job_service(db, entity_id)
        return JobTimelineSummary.model_validate(job)
    return None


@router.get("", response_model=EventListResponse)
def list_events(
    db: Session = Depends(get_db),
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    actor_type: str | None = Query(None),
    actor_id: str | None = Query(None),
    actor_label: str | None = Query(None),
    source: str | None = Query(None),
    request_id: str | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
) -> EventListResponse:
    if (entity_type is None) != (entity_id is None):
        detail = "entity_type and entity_id must be provided together"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    entity_summary: EventEntitySummary | None = None
    if entity_type and entity_id:
        try:
            entity_summary = _load_entity_summary(db, entity_type, entity_id)
        except (DocumentNotFoundError, ConfigurationNotFoundError, JobNotFoundError) as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        result = list_events_service(
            db,
            limit=limit,
            offset=offset,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_label=actor_label,
            source=source,
            request_id=request_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [_to_response(event) for event in result.events]
    return EventListResponse(
        items=items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        entity=entity_summary,
    )


__all__ = ["router"]
