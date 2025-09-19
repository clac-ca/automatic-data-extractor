"""HTTP endpoints for job resources."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditEvent, Job
from ..schemas import (
    AuditEventListResponse,
    AuditEventResponse,
    JobCreate,
    JobResponse,
    JobUpdate,
)
from ..services.audit_log import list_entity_events
from ..services.configurations import (
    ActiveConfigurationNotFoundError,
    ConfigurationMismatchError,
    ConfigurationNotFoundError,
)
from ..services.jobs import (
    InvalidJobStatusError,
    JobImmutableError,
    JobNotFoundError,
    create_job,
    get_job,
    list_jobs,
    update_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_response(job: Job) -> JobResponse:
    return JobResponse.model_validate(job)


def _audit_to_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse.model_validate(event)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(payload: JobCreate, db: Session = Depends(get_db)) -> JobResponse:
    """Create a job for the supplied document type."""

    try:
        job = create_job(
            db,
            document_type=payload.document_type,
            created_by=payload.created_by,
            input_payload=payload.input,
            status=payload.status,
            outputs=payload.outputs,
            metrics=payload.metrics,
            logs=payload.logs,
            configuration_id=payload.configuration_id,
            audit_actor_type="user",
            audit_actor_label=payload.created_by,
            audit_source="api",
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActiveConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ConfigurationMismatchError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidJobStatusError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _to_response(job)


@router.get("", response_model=list[JobResponse])
def list_jobs_endpoint(db: Session = Depends(get_db)) -> list[JobResponse]:
    """Return all jobs ordered by creation time."""

    jobs = list_jobs(db)
    return [_to_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    """Return a single job by identifier."""

    try:
        job = get_job(db, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(job)


@router.get("/{job_id}/audit-events", response_model=AuditEventListResponse)
def list_job_audit_events(
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
) -> AuditEventListResponse:
    try:
        get_job(db, job_id)
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

    items = [_audit_to_response(event) for event in result.events]
    return AuditEventListResponse(
        items=items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.patch("/{job_id}", response_model=JobResponse)
def update_job_endpoint(
    job_id: str, payload: JobUpdate, db: Session = Depends(get_db)
) -> JobResponse:
    """Update mutable job fields."""

    update_kwargs = payload.model_dump(exclude_unset=True)

    try:
        job = update_job(
            db,
            job_id,
            **update_kwargs,
            audit_actor_type="system",
            audit_actor_label="api",
            audit_source="api",
        )
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobImmutableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidJobStatusError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _to_response(job)


@router.delete("/{job_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
def delete_job_endpoint(job_id: str) -> None:
    """Jobs are immutable audit records and cannot be deleted."""

    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Jobs cannot be deleted once created",
    )


__all__ = ["router"]

