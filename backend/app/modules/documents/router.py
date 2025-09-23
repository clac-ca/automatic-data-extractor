"""API routes exposing document metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_documents_service
from .exceptions import DocumentNotFoundError
from .schemas import DocumentRecord
from .service import DocumentsService


router = APIRouter(tags=["documents"])


@cbv(router)
class DocumentsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: DocumentsService = Depends(get_documents_service)

    @router.get(
        "/documents",
        response_model=list[DocumentRecord],
        status_code=status.HTTP_200_OK,
        summary="List documents for the active workspace",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def list_documents(
        self,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        produced_by_job_id: str | None = Query(None),
    ) -> list[DocumentRecord]:
        documents = await self.service.list_documents(
            limit=limit,
            offset=offset,
            produced_by_job_id=produced_by_job_id,
        )
        return documents

    @router.get(
        "/documents/{document_id}",
        response_model=DocumentRecord,
        status_code=status.HTTP_200_OK,
        summary="Retrieve a single document by identifier",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def read_document(self, document_id: str) -> DocumentRecord:
        try:
            return await self.service.get_document(document_id=document_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
