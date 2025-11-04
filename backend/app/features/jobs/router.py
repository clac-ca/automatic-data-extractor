"""FastAPI router exposing job orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Response, Security, status
from fastapi.responses import FileResponse

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.features.users.models import User
from backend.app.shared.core.schema import ErrorMessage

from .dependencies import get_jobs_service
from .exceptions import (
    JobNotFoundError,
    JobQueueFullError,
    JobQueueUnavailableError,
    JobSubmissionError,
)
from .schemas import JobArtifact, JobRecord, JobSubmitRequest
from .service import JobsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/jobs",
    tags=["jobs"],
    dependencies=[Security(require_authenticated)],
)


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=JobRecord,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a job",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorMessage},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorMessage},
    },
)
async def submit_job(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    payload: JobSubmitRequest,
    service: Annotated[JobsService, Depends(get_jobs_service)],
    response: Response,
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> JobRecord:
    try:
        record = await service.submit_job(
            workspace_id=workspace_id,
            request=payload,
            actor=actor,
        )
        location = f"/api/v1/workspaces/{workspace_id}/jobs/{record.job_id}"
        response.headers["Location"] = location
        return record
    except JobSubmissionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except JobQueueFullError as exc:
        headers = {"Retry-After": str(10)}
        detail: dict[str, object] = {
            "message": str(exc),
            "queue_size": exc.queue_size,
            "max_size": exc.max_size,
            "max_concurrency": exc.max_concurrency,
        }
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=detail, headers=headers) from exc
    except JobQueueUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get(
    "/{job_id}",
    response_model=JobRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve job details",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_job(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    job_id: Annotated[str, PathParam(min_length=1)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> JobRecord:
    try:
        return await service.get_job(workspace_id=workspace_id, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{job_id}/artifact",
    response_model=JobArtifact,
    status_code=status.HTTP_200_OK,
    summary="Retrieve job artifact JSON",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_artifact(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    job_id: Annotated[str, PathParam(min_length=1)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> JobArtifact:
    try:
        return await service.load_artifact(workspace_id=workspace_id, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{job_id}/output",
    status_code=status.HTTP_200_OK,
    summary="Download normalized workbook",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def get_output(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    job_id: Annotated[str, PathParam(min_length=1)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> FileResponse:
    try:
        path = await service.output_path(workspace_id=workspace_id, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media_type, filename="normalized.xlsx")


__all__ = ["router"]
@router.post(
    "/{job_id}/retry",
    dependencies=[Security(require_csrf)],
    response_model=JobRecord,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a job",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorMessage},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorMessage},
    },
)
async def retry_job(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    job_id: Annotated[str, PathParam(min_length=1)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
    response: Response,
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> JobRecord:
    try:
        record = await service.retry_job(
            workspace_id=workspace_id,
            job_id=job_id,
            actor=actor,
        )
        location = f"/api/v1/workspaces/{workspace_id}/jobs/{record.job_id}"
        response.headers["Location"] = location
        return record
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobQueueFullError as exc:
        headers = {"Retry-After": str(10)}
        detail: dict[str, object] = {
            "message": str(exc),
            "queue_size": exc.queue_size,
            "max_size": exc.max_size,
            "max_concurrency": exc.max_concurrency,
        }
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=detail, headers=headers) from exc
    except JobQueueUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
