from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..documents.exceptions import DocumentNotFoundError
from ..jobs.exceptions import JobNotFoundError
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_results_service
from .exceptions import ExtractedTableNotFoundError
from .schemas import ExtractedTableRecord
from .service import ExtractionResultsService


router = APIRouter(tags=["results"])


@cbv(router)
class ExtractionResultsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: ExtractionResultsService = Depends(get_results_service)

    @router.get(
        "/jobs/{job_id}/tables",
        response_model=list[ExtractedTableRecord],
        status_code=status.HTTP_200_OK,
        summary="List extracted tables for a job",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def list_job_tables(self, job_id: str) -> list[ExtractedTableRecord]:
        try:
            return await self.service.list_tables_for_job(job_id=job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.get(
        "/jobs/{job_id}/tables/{table_id}",
        response_model=ExtractedTableRecord,
        status_code=status.HTTP_200_OK,
        summary="Retrieve an extracted table for a job",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:jobs:read"}, require_workspace=True)
    async def read_job_table(
        self, job_id: str, table_id: str
    ) -> ExtractedTableRecord:
        try:
            return await self.service.get_table(job_id=job_id, table_id=table_id)
        except JobNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ExtractedTableNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.get(
        "/documents/{document_id}/tables",
        response_model=list[ExtractedTableRecord],
        status_code=status.HTTP_200_OK,
        summary="List extracted tables for a document",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def list_document_tables(
        self, document_id: str
    ) -> list[ExtractedTableRecord]:
        try:
            return await self.service.list_tables_for_document(document_id=document_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
