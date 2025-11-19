"""Jobs router providing submission and retrieval endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Security,
    status,
)

from ade_api.features.jobs.models import JobStatus
from ade_api.features.jobs.schemas import JobRecord, JobSubmissionRequest
from ade_api.features.jobs.service import (
    JobConfigurationMissingError,
    JobDocumentMissingError,
    JobsService,
)
from ade_api.features.users.models import User
from ade_api.shared.dependency import (
    get_jobs_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["jobs"],
    dependencies=[Security(require_authenticated)],
)

jobs_service_dependency = Depends(get_jobs_service)


@router.post(
    "/jobs",
    response_model=JobRecord,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def submit_job_endpoint(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    payload: JobSubmissionRequest,
    service: JobsService = jobs_service_dependency,
    actor: Annotated[
        User | None,
        Security(
            require_workspace("Workspace.Jobs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ] = None,
) -> JobRecord:
    try:
        return await service.submit_job(
            workspace_id=workspace_id,
            payload=payload,
            actor=actor,
        )
    except JobDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobConfigurationMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[JobRecord])
async def list_jobs_endpoint(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    service: JobsService = jobs_service_dependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    input_document_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    _actor: Annotated[
        User | None,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ] = None,
) -> list[JobRecord]:
    job_status: JobStatus | None = None
    if status_filter:
        try:
            job_status = JobStatus(status_filter)
        except ValueError as exc:  # pragma: no cover - FastAPI handles validation
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return await service.list_jobs(
        workspace_id=workspace_id,
        status=job_status,
        input_document_id=input_document_id,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=JobRecord)
async def read_job_endpoint(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    job_id: Annotated[str, Path(min_length=1, description="Job identifier")],
    service: JobsService = jobs_service_dependency,
    _actor: Annotated[
        User | None,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ] = None,
) -> JobRecord:
    job = await service.get_job(workspace_id=workspace_id, job_id=job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


__all__ = ["router"]
