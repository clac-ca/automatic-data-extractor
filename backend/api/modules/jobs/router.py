"""FastAPI routes for job submission and tracking."""

from fastapi import Body, Depends, HTTPException, Query, Request, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..configurations.exceptions import (
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
)
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.routing import workspace_scoped_router
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_jobs_service
from .exceptions import (
    InputDocumentNotFoundError,
    JobExecutionError,
    JobNotFoundError,
)
from .schemas import JobRecord, JobSubmissionRequest
from .service import JobsService

JOB_SUBMISSION_BODY = Body(...)

router = workspace_scoped_router(tags=["jobs"])


@cbv(router)
class JobsRoutes:
    request: Request
    session: AsyncSession = Depends(get_session)  # noqa: B008
    selection: WorkspaceContext = Depends(bind_workspace_context)  # noqa: B008
    service: JobsService = Depends(get_jobs_service)  # noqa: B008

    @router.get(
        "/jobs",
        response_model=list[JobRecord],
        status_code=status.HTTP_200_OK,
        summary="List jobs",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def list_jobs(
        self,
        limit: int = Query(50, ge=1, le=200),  # noqa: B008
        offset: int = Query(0, ge=0),  # noqa: B008
        status_filter: str | None = Query(None, alias="status"),  # noqa: B008
        input_document_id: str | None = Query(None),  # noqa: B008
    ) -> list[JobRecord]:
        try:
            return await self.service.list_jobs(
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
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def read_job(self, job_id: str) -> JobRecord:
        try:
            return await self.service.get_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post(
        "/jobs",
        response_model=JobRecord,
        status_code=status.HTTP_201_CREATED,
        summary="Submit a job",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:write"}, require_workspace=True)
    async def submit_job(
        self,
        payload: JobSubmissionRequest = JOB_SUBMISSION_BODY,
    ) -> JobRecord:
        try:
            return await self.service.submit_job(
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
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
            ) from exc


__all__ = ["router"]
