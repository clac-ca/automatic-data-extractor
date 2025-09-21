"""HTTP endpoints for job resources."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..services import auth as auth_service
from ..db import get_db
from ..models import Event, Job
from ..schemas import (
    EventListResponse,
    EventResponse,
    JobCreate,
    JobResponse,
    JobTimelineSummary,
    JobUpdate,
)
from ..services.events import list_entity_events
from ..services.configurations import (
    ActiveConfigurationNotFoundError,
    ConfigurationMismatchError,
    ConfigurationNotFoundError,
)
from ..services.jobs import (
    InputDocumentNotFoundError,
    InvalidJobStatusError,
    JobImmutableError,
    JobNotFoundError,
    build_job_projection,
    create_job,
    get_job,
    list_jobs,
    update_job,
)

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    # Resolve authentication once per request so handlers can reuse the cached identity.
    dependencies=[Depends(auth_service.get_authenticated_identity)],
)


def _to_response(db: Session, job: Job) -> JobResponse:
    projection = build_job_projection(db, job)
    return JobResponse.model_validate(projection)


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse.model_validate(event)


@router.post(
    "",
    response_model=JobResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_job_endpoint(
    payload: JobCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Create a job for the supplied document type."""

    identity = auth_service.get_cached_authenticated_identity(request)
    actor_defaults = auth_service.event_actor_from_identity(identity)

    try:
        job = create_job(
            db,
            document_type=payload.document_type,
            created_by=payload.created_by,
            input_document_id=payload.input_document_id,
            status=payload.status,
            metrics=payload.metrics,
            logs=payload.logs,
            configuration_id=payload.configuration_id,
            event_actor_type=actor_defaults["actor_type"],
            event_actor_id=actor_defaults["actor_id"],
            event_actor_label=actor_defaults["actor_label"],
            event_source="api",
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActiveConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ConfigurationMismatchError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidJobStatusError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except InputDocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _to_response(db, job)


@router.get(
    "",
    response_model=list[JobResponse],
    response_model_exclude_none=True,
)
def list_jobs_endpoint(
    db: Session = Depends(get_db),
    *,
    input_document_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[JobResponse]:
    """Return all jobs ordered by creation time."""

    jobs = list_jobs(
        db,
        input_document_id=input_document_id,
        limit=limit,
        offset=offset,
    )
    return [_to_response(db, job) for job in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    response_model_exclude_none=True,
)
def get_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Return a single job by identifier."""

    try:
        job = get_job(db, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(db, job)


@router.get("/{job_id}/events", response_model=EventListResponse)
def list_job_events(
    job_id: str,
    db: Session = Depends(get_db),
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    request_id: str | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
    ) -> EventListResponse:
    try:
        job = get_job(db, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        result = list_entity_events(
            db,
            entity_type="job",
            entity_id=job_id,
            limit=limit,
            offset=offset,
            event_type=event_type,
            source=source,
            request_id=request_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [_event_to_response(event) for event in result.events]
    return EventListResponse(
        items=items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        entity=JobTimelineSummary.model_validate(job),
    )


@router.patch(
    "/{job_id}",
    response_model=JobResponse,
    response_model_exclude_none=True,
)
def update_job_endpoint(
    job_id: str,
    payload: JobUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Update mutable job fields."""

    update_kwargs = payload.model_dump(exclude_unset=True)

    identity = auth_service.get_cached_authenticated_identity(request)
    actor_defaults = auth_service.event_actor_from_identity(identity)

    try:
        job = update_job(
            db,
            job_id,
            **update_kwargs,
            event_actor_type=actor_defaults["actor_type"],
            event_actor_id=actor_defaults["actor_id"],
            event_actor_label=actor_defaults["actor_label"],
            event_source="api",
        )
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobImmutableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidJobStatusError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _to_response(db, job)


@router.delete("/{job_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
def delete_job_endpoint(job_id: str) -> None:
    """Jobs are immutable records and cannot be deleted."""

    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Jobs cannot be deleted once created",
    )


__all__ = ["router"]

