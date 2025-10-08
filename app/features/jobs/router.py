from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_app_settings
from app.core.config import Settings
from app.core.schema import ErrorMessage
from app.db.session import get_session

from ..auth.dependencies import bind_current_user
from ..configurations.exceptions import (
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
)
from ..users.models import User
from ..workspaces.dependencies import require_workspace_access
from ..workspaces.schemas import WorkspaceProfile
from .exceptions import (
    InputDocumentNotFoundError,
    JobExecutionError,
    JobNotFoundError,
)
from .schemas import JobFailureMessage, JobRecord, JobSubmissionRequest
from .service import JobsService

JOB_SUBMISSION_BODY = Body(...)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["jobs"])


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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Jobs.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    input_document_id: str | None = Query(None),
) -> list[JobRecord]:
    service = JobsService(session=session, settings=settings)
    try:
        return await service.list_jobs(
            workspace_id=workspace.workspace_id,
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
    job_id: Annotated[str, Path(min_length=1, description="Job identifier")],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Jobs.Read"],
        ),
    ],
    current_user: Annotated[User, Depends(bind_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> JobRecord:
    service = JobsService(session=session, settings=settings)
    try:
        return await service.get_job(
            workspace_id=workspace.workspace_id,
            job_id=job_id,
        )
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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Jobs.ReadWrite"],
        ),
    ],
    current_user: Annotated[User, Depends(bind_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    *,
    payload: JobSubmissionRequest = JOB_SUBMISSION_BODY,
) -> JobRecord:
    service = JobsService(session=session, settings=settings)
    try:
        return await service.submit_job(
            workspace_id=workspace.workspace_id,
            input_document_id=payload.input_document_id,
            configuration_id=payload.configuration_id,
            configuration_version=payload.configuration_version,
            actor=current_user,
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
