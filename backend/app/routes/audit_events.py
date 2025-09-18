"""Audit event API endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditEvent
from ..schemas import AuditEventListResponse, AuditEventResponse
from ..services.audit_log import list_events as list_events_service

router = APIRouter(prefix="/audit-events", tags=["audit"])


def _to_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse.model_validate(event)


@router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    db: Session = Depends(get_db),
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    source: str | None = Query(None),
    request_id: str | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
) -> AuditEventListResponse:
    if (entity_type is None) ^ (entity_id is None):
        detail = "entity_type and entity_id must be provided together"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    try:
        result = list_events_service(
            db,
            limit=limit,
            offset=offset,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            request_id=request_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [_to_response(event) for event in result.events]
    return AuditEventListResponse(items=items, total=result.total, limit=result.limit, offset=result.offset)


__all__ = ["router"]
