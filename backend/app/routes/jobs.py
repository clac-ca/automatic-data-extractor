"""HTTP endpoints for job resources."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Job
from ..schemas import JobCreate, JobResponse, JobUpdate
from ..services.configuration_revisions import (
    ActiveConfigurationRevisionNotFoundError,
    ConfigurationRevisionMismatchError,
    ConfigurationRevisionNotFoundError,
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
            configuration_revision_id=payload.configuration_revision_id,
        )
    except ConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActiveConfigurationRevisionNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ConfigurationRevisionMismatchError as exc:
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


@router.patch("/{job_id}", response_model=JobResponse)
def update_job_endpoint(
    job_id: str, payload: JobUpdate, db: Session = Depends(get_db)
) -> JobResponse:
    """Update mutable job fields."""

    update_kwargs = payload.model_dump(exclude_unset=True)

    try:
        job = update_job(db, job_id, **update_kwargs)
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

