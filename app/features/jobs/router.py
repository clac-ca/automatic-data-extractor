from __future__ import annotations

from typing import Annotated

from fastapi import Body, Depends, HTTPException, Query, status

from app.core.schema import ErrorMessage

from ..auth.security import access_control
from ..configurations.exceptions import (
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
)
from ..workspaces.dependencies import require_workspace_context
from ..workspaces.routing import workspace_scoped_router
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_jobs_service
from .exceptions import (
    InputDocumentNotFoundError,
    JobExecutionError,
    JobNotFoundError,
)
from .schemas import JobFailureMessage, JobRecord, JobSubmissionRequest
from .service import JobsService

JOB_SUBMISSION_BODY = Body(...)

router = workspace_scoped_router(tags=["jobs"])

WorkspaceContextDep = Annotated[WorkspaceContext, Depends(require_workspace_context)]
JobsReadServiceDep = Annotated[
    JobsService,
    Depends(
        access_control(
            permissions={"workspace:jobs:read"},
            require_workspace=True,
            service_dependency=get_jobs_service,
        )
    ),
]
JobsWriteServiceDep = Annotated[
    JobsService,
    Depends(
        access_control(
            permissions={"workspace:jobs:write"},
            require_workspace=True,
            service_dependency=get_jobs_service,
        )
    ),
]


@router.get(
    "/jobs",
    response_model=list[JobRecord],
    status_code=status.HTTP_200_OK,
    summary="List jobs",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Query parameters are invalid or unsupported.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list jobs.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow job access.",
            "model": ErrorMessage,
        },
    },
)
async def list_jobs(
    _: WorkspaceContextDep,
    service: JobsReadServiceDep,
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    input_document_id: str | None = Query(None),
) -> list[JobRecord]:
    try:
        return await service.list_jobs(
            limit=limit,
            offset=offset,
            status=status_filter,
            input_document_id=input_document_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=JobRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a job",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read jobs.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow job access.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def read_job(
    job_id: str,
    _: WorkspaceContextDep,
    service: JobsReadServiceDep,
) -> JobRecord:
    try:
        return await service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/jobs",
    response_model=JobRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a job",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Configuration mismatch or invalid job parameters.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to submit jobs.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow job submission.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Input document or configuration could not be found.",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Job failed during execution.",
            "model": JobFailureMessage,
        },
    },
)
async def submit_job(
    _: WorkspaceContextDep,
    service: JobsWriteServiceDep,
    *,
    payload: JobSubmissionRequest = JOB_SUBMISSION_BODY,
) -> JobRecord:
    try:
        return await service.submit_job(
            input_document_id=payload.input_document_id,
            configuration_id=payload.configuration_id,
            configuration_version=payload.configuration_version,
        )
    except InputDocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationVersionMismatchError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except JobExecutionError as exc:
        detail = {
            "error": "job_failed",
            "job_id": exc.job_id,
            "message": str(exc),
        }
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail) from exc


__all__ = ["router"]
