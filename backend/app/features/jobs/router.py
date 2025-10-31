"""FastAPI router exposing job orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Security, status
from fastapi.responses import FileResponse

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.features.users.models import User
from backend.app.shared.core.schema import ErrorMessage

from .dependencies import get_jobs_service
from .exceptions import JobNotFoundError, JobSubmissionError
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
    status_code=status.HTTP_201_CREATED,
    summary="Submit a job",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorMessage},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def submit_job(
    workspace_id: Annotated[str, PathParam(min_length=1)],
    payload: JobSubmitRequest,
    service: Annotated[JobsService, Depends(get_jobs_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Jobs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> JobRecord:
    try:
        return await service.submit_job(
            workspace_id=workspace_id,
            request=payload,
            actor=actor,
        )
    except JobSubmissionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
