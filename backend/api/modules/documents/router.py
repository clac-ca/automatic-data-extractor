"""FastAPI routes for document upload and retrieval."""

import json
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_documents_service
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .schemas import DocumentDeleteRequest, DocumentRecord
from .service import DocumentsService

router = APIRouter(tags=["documents"])


def _parse_metadata(metadata: str | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    try:
        decoded = json.loads(metadata)
    except json.JSONDecodeError as exc:  # pragma: no cover - validation guard
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="metadata must be valid JSON",
        ) from exc
    if not isinstance(decoded, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="metadata must be a JSON object",
        )
    return decoded


@cbv(router)
class DocumentsRoutes:
    session: AsyncSession = Depends(get_session)  # noqa: B008
    selection: WorkspaceContext = Depends(bind_workspace_context)  # noqa: B008
    service: DocumentsService = Depends(get_documents_service)  # noqa: B008

    @router.post(
        "/documents",
        response_model=DocumentRecord,
        status_code=status.HTTP_201_CREATED,
        summary="Upload a document",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:write"}, require_workspace=True)
    async def upload_document(
        self,
        file: UploadFile = File(...),  # noqa: B008
        metadata: str | None = Form(None),  # noqa: B008
        expires_at: str | None = Form(None),  # noqa: B008
    ) -> DocumentRecord:
        payload = _parse_metadata(metadata)
        try:
            return await self.service.create_document(
                upload=file,
                metadata=payload,
                expires_at=expires_at,
            )
        except DocumentTooLargeError as exc:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
            ) from exc
        except InvalidDocumentExpirationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @router.get(
        "/documents",
        response_model=list[DocumentRecord],
        status_code=status.HTTP_200_OK,
        summary="List documents",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def list_documents(
        self,
        limit: int = Query(50, ge=1, le=200),  # noqa: B008
        offset: int = Query(0, ge=0),  # noqa: B008
    ) -> list[DocumentRecord]:
        return await self.service.list_documents(limit=limit, offset=offset)

    @router.get(
        "/documents/{document_id}",
        response_model=DocumentRecord,
        status_code=status.HTTP_200_OK,
        summary="Retrieve document metadata",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def read_document(self, document_id: str) -> DocumentRecord:
        try:
            return await self.service.get_document(document_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.get(
        "/documents/{document_id}/download",
        summary="Download a stored document",
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def download_document(self, document_id: str) -> StreamingResponse:
        try:
            record, stream = await self.service.stream_document(document_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except DocumentFileMissingError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        media_type = record.content_type or "application/octet-stream"
        filename = record.original_filename.replace('"', "")
        response = StreamingResponse(stream, media_type=media_type)
        response.headers[
            "Content-Disposition"
        ] = f'attachment; filename="{filename}"'
        return response

    @router.delete(
        "/documents/{document_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Soft delete a document",
    )
    @access_control(permissions={"workspace:documents:write"}, require_workspace=True)
    async def delete_document(
        self,
        document_id: str,
        payload: DocumentDeleteRequest | None = Body(default=None),  # noqa: B008
    ) -> None:
        try:
            await self.service.delete_document(
                document_id=document_id,
                reason=payload.reason if payload else None,
            )
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
