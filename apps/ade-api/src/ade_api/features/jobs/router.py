"""Jobs router providing submission and retrieval endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Security,
    status,
)
from fastapi.responses import FileResponse

from ade_api.features.jobs.models import JobStatus
from ade_api.features.jobs.schemas import (
    JobOutputFile,
    JobOutputListing,
    JobRecord,
    JobSubmissionRequest,
)
from ade_api.features.jobs.service import (
    JobConfigurationMissingError,
    JobArtifactMissingError,
    JobDocumentMissingError,
    JobLogsMissingError,
    JobNotFoundError,
    JobOutputMissingError,
    JobsService,
)
from ade_api.features.runs.service import RunEnvironmentNotReadyError
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
    background_tasks: BackgroundTasks,
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
            background_tasks=background_tasks,
        )
    except JobDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobConfigurationMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunEnvironmentNotReadyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


@router.get(
    "/jobs/{job_id}/artifact",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Artifact unavailable"}},
)
async def download_job_artifact(
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
):
    try:
        artifact_path = await service.get_artifact_path(
            workspace_id=workspace_id, job_id=job_id
        )
    except (JobNotFoundError, JobArtifactMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        path=artifact_path,
        media_type="application/json",
        filename=artifact_path.name,
    )


@router.get(
    "/jobs/{job_id}/logs",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Logs unavailable"}},
)
async def download_job_logs(
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
):
    try:
        logs_path = await service.get_logs_path(workspace_id=workspace_id, job_id=job_id)
    except (JobNotFoundError, JobLogsMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        path=logs_path,
        media_type="application/x-ndjson",
        filename=logs_path.name,
    )


@router.get(
    "/jobs/{job_id}/outputs",
    response_model=JobOutputListing,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Outputs unavailable"}},
)
async def list_job_outputs(
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
) -> JobOutputListing:
    try:
        files = await service.list_output_files(
            workspace_id=workspace_id, job_id=job_id
        )
    except (JobNotFoundError, JobOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    entries = [JobOutputFile(path=path, byte_size=size) for path, size in files]
    return JobOutputListing(files=entries)


@router.get(
    "/jobs/{job_id}/outputs/{output_path:path}",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Output not found"}},
)
async def download_job_output(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    job_id: Annotated[str, Path(min_length=1, description="Job identifier")],
    output_path: str,
    service: JobsService = jobs_service_dependency,
    _actor: Annotated[
        User | None,
        Security(
            require_workspace("Workspace.Jobs.Read"),
            scopes=["{workspace_id}"],
        ),
    ] = None,
):
    try:
        path = await service.resolve_output_file(
            workspace_id=workspace_id,
            job_id=job_id,
            relative_path=output_path,
        )
    except (JobNotFoundError, JobOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(path=path, filename=path.name)


__all__ = ["router"]
