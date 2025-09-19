"""HTTP endpoints for configuration resources."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import TypeAdapter, ValidationError
from pydantic.types import StringConstraints
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditEvent, Configuration
from ..schemas import (
    AuditEventListResponse,
    AuditEventResponse,
    ConfigurationCreate,
    ConfigurationResponse,
    ConfigurationUpdate,
)
from ..services.audit_log import list_entity_events
from ..services.configurations import (
    ActiveConfigurationNotFoundError,
    ConfigurationNotFoundError,
    create_configuration,
    delete_configuration,
    get_active_configuration,
    get_configuration,
    list_configurations,
    update_configuration,
)

router = APIRouter(prefix="/configurations", tags=["configurations"])

_document_type_adapter = TypeAdapter(
    Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ]
)


def _to_response(configuration: Configuration) -> ConfigurationResponse:
    """Convert ORM objects to response models."""

    return ConfigurationResponse.model_validate(configuration)


def _audit_to_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse.model_validate(event)


@router.post(
    "",
    response_model=ConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_configuration_endpoint(
    payload: ConfigurationCreate, db: Session = Depends(get_db)
) -> ConfigurationResponse:
    """Create a new configuration version."""

    try:
        configuration = create_configuration(
            db,
            document_type=payload.document_type,
            title=payload.title,
            payload=payload.payload,
            is_active=payload.is_active,
            audit_actor_type="system",
            audit_actor_label="api",
            audit_source="api",
        )
    except IntegrityError as exc:
        db.rollback()
        detail = (
            "An active configuration already exists for "
            f"'{payload.document_type}'. Only one revision may be active at a time."
        )
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
    return _to_response(configuration)


@router.get("", response_model=list[ConfigurationResponse])
def list_configurations_endpoint(
    db: Session = Depends(get_db),
) -> list[ConfigurationResponse]:
    """Return all configurations."""

    configurations = list_configurations(db)
    return [_to_response(configuration) for configuration in configurations]


@router.get("/{configuration_id}", response_model=ConfigurationResponse)
def get_configuration_endpoint(
    configuration_id: str, db: Session = Depends(get_db)
) -> ConfigurationResponse:
    """Return a single configuration version."""

    try:
        configuration = get_configuration(db, configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(configuration)


@router.get("/active/{document_type}", response_model=ConfigurationResponse)
def get_active_configuration_endpoint(
    document_type: str, db: Session = Depends(get_db)
) -> ConfigurationResponse:
    """Return the active configuration for the given document type."""

    try:
        normalized_name = _document_type_adapter.validate_python(document_type)
    except ValidationError as exc:
        detail = [
            {
                **error,
                "loc": ["path", "document_type", *error.get("loc", ())],
            }
            for error in exc.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    try:
        configuration = get_active_configuration(db, normalized_name)
    except ActiveConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(configuration)


@router.get("/{configuration_id}/audit-events", response_model=AuditEventListResponse)
def list_configuration_audit_events(
    configuration_id: str,
    db: Session = Depends(get_db),
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    request_id: str | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
) -> AuditEventListResponse:
    try:
        get_configuration(db, configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        result = list_entity_events(
            db,
            entity_type="configuration",
            entity_id=configuration_id,
            limit=limit,
            offset=offset,
            event_type=event_type,
            source=source,
            request_id=request_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [_audit_to_response(event) for event in result.events]
    return AuditEventListResponse(
        items=items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.patch("/{configuration_id}", response_model=ConfigurationResponse)
def update_configuration_endpoint(
    configuration_id: str,
    payload: ConfigurationUpdate,
    db: Session = Depends(get_db),
) -> ConfigurationResponse:
    """Update configuration metadata."""

    update_kwargs = payload.model_dump(exclude_unset=True)
    try:
        configuration = update_configuration(
            db,
            configuration_id,
            **update_kwargs,
            audit_actor_type="system",
            audit_actor_label="api",
            audit_source="api",
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        existing = get_configuration(db, configuration_id)
        detail = (
            "An active configuration already exists for "
            f"'{existing.document_type}'. Only one revision may be active at a time."
        )
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
    return _to_response(configuration)


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration_endpoint(
    configuration_id: str, db: Session = Depends(get_db)
) -> Response:
    """Delete a configuration version."""

    try:
        delete_configuration(db, configuration_id)
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
