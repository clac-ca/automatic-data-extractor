"""FastAPI router for job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..events.dependencies import get_events_service
from ..events.schemas import EventRecord
from ..events.service import EventsService
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_jobs_service
from .exceptions import InputDocumentNotFoundError, JobNotFoundError
from .schemas import JobRecord, JobSubmissionRequest
from ..configurations.exceptions import (
    ActiveConfigurationNotFoundError,
    ConfigurationMismatchError,
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
    ConfigurationVersionNotFoundError,
)
from .service import JobsService


router = APIRouter(tags=["jobs"])


async def _parse_job_submission(request: Request) -> JobSubmissionRequest:
    payload = await request.json()
    return JobSubmissionRequest.model_validate(payload)


@cbv(router)
class JobsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: JobsService = Depends(get_jobs_service)
    events_service: EventsService = Depends(get_events_service)

    @router.post(
        "/jobs",
        response_model=JobRecord,
        status_code=status.HTTP_201_CREATED,
        summary="Queue a processing job for an uploaded document",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:write"}, require_workspace=True)
    async def create_job(
        self,
        payload: JobSubmissionRequest = Depends(_parse_job_submission),
    ) -> JobRecord:
        try:
            return await self.service.create_job(
                input_document_id=payload.input_document_id,
                document_type=payload.document_type,
                configuration_id=payload.configuration_id,
                configuration_version=payload.configuration_version,
            )
        except InputDocumentNotFoundError as exc:
            detail = {"error": "input_document_not_found", "message": str(exc)}
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
        except ConfigurationNotFoundError as exc:
            detail = {"error": "configuration_not_found", "message": str(exc)}
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
        except ConfigurationVersionNotFoundError as exc:
            detail = {
                "error": "configuration_version_not_found",
                "message": str(exc),
            }
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
        except ActiveConfigurationNotFoundError as exc:
            detail = {
                "error": "active_configuration_missing",
                "message": str(exc),
            }
            raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
        except ConfigurationMismatchError as exc:
            detail = {"error": "configuration_mismatch", "message": str(exc)}
            raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
        except ConfigurationVersionMismatchError as exc:
            detail = {
                "error": "configuration_version_mismatch",
                "message": str(exc),
            }
            raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc

    @router.get(
        "/jobs",
        response_model=list[JobRecord],
        status_code=status.HTTP_200_OK,
        summary="List jobs for the active workspace",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def list_jobs(
        self,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        input_document_id: str | None = Query(None),
    ) -> list[JobRecord]:
        jobs = await self.service.list_jobs(
            limit=limit,
            offset=offset,
            input_document_id=input_document_id,
        )
        return jobs

    @router.get(
        "/jobs/{job_id}",
        response_model=JobRecord,
        status_code=status.HTTP_200_OK,
        summary="Retrieve a single job by identifier",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def read_job(self, job_id: str) -> JobRecord:
        try:
            return await self.service.get_job(job_id=job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.get(
        "/jobs/{job_id}/events",
        response_model=list[EventRecord],
        status_code=status.HTTP_200_OK,
        summary="List events recorded for a job",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def list_job_events(
        self,
        job_id: str,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> list[EventRecord]:
        try:
            await self.service.get_job(job_id=job_id, emit_event=False)
        except JobNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        events = await self.events_service.list_job_events(
            job_id=job_id,
            limit=limit,
            offset=offset,
        )
        return events


__all__ = ["router"]
