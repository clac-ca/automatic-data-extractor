from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.schema import ErrorMessage
from ..auth.security import access_control
from ..documents.exceptions import DocumentNotFoundError
from ..jobs.exceptions import JobNotFoundError
from ..workspaces.dependencies import require_workspace_context
from ..workspaces.routing import workspace_scoped_router
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_results_service
from .exceptions import ExtractedTableNotFoundError, JobResultsUnavailableError
from .schemas import ExtractedTableRecord, JobResultsUnavailableMessage
from .service import ExtractionResultsService

router = workspace_scoped_router(tags=["results"])

WorkspaceContextDep = Annotated[WorkspaceContext, Depends(require_workspace_context)]
JobResultsServiceDep = Annotated[
    ExtractionResultsService,
    Depends(
        access_control(
            permissions={"workspace:jobs:read"},
            require_workspace=True,
            service_dependency=get_results_service,
        )
    ),
]
DocumentResultsServiceDep = Annotated[
    ExtractionResultsService,
    Depends(
        access_control(
            permissions={"workspace:documents:read"},
            require_workspace=True,
            service_dependency=get_results_service,
        )
    ),
]


@router.get(
    "/jobs/{job_id}/tables",
    response_model=list[ExtractedTableRecord],
    status_code=status.HTTP_200_OK,
    summary="List extracted tables for a job",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read job results.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow access to this job's results.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found within the workspace.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Job has not produced results yet or is still running.",
            "model": JobResultsUnavailableMessage,
        },
    },
)
async def list_job_tables(
    job_id: str,
    _: WorkspaceContextDep,
    service: JobResultsServiceDep,
) -> list[ExtractedTableRecord]:
    try:
        return await service.list_tables_for_job(job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobResultsUnavailableError as exc:
        detail = {
            "error": "job_results_unavailable",
            "job_id": exc.job_id,
            "status": exc.status,
            "message": str(exc),
        }
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get(
    "/jobs/{job_id}/tables/{table_id}",
    response_model=ExtractedTableRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an extracted table for a job",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read job results.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow access to this job's results.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Job or table not found within the workspace.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Job has not produced results yet or is still running.",
            "model": JobResultsUnavailableMessage,
        },
    },
)
async def read_job_table(
    job_id: str,
    table_id: str,
    _: WorkspaceContextDep,
    service: JobResultsServiceDep,
) -> ExtractedTableRecord:
    try:
        return await service.get_table(job_id=job_id, table_id=table_id)
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobResultsUnavailableError as exc:
        detail = {
            "error": "job_results_unavailable",
            "job_id": exc.job_id,
            "status": exc.status,
            "message": str(exc),
        }
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail) from exc
    except ExtractedTableNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/documents/{document_id}/tables",
    response_model=list[ExtractedTableRecord],
    status_code=status.HTTP_200_OK,
    summary="List extracted tables for a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read document results.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow access to document results.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def list_document_tables(
    document_id: str,
    _: WorkspaceContextDep,
    service: DocumentResultsServiceDep,
) -> list[ExtractedTableRecord]:
    try:
        return await service.list_tables_for_document(document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
