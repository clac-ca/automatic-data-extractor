"""API routes exposing document metadata."""

import json
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.security import access_control
from ..events.dependencies import get_events_service
from ..events.schemas import EventRecord
from ..events.service import EventsService
from ..workspaces.dependencies import bind_workspace_context
from ..workspaces.schemas import WorkspaceContext
from .dependencies import get_documents_service
from ..jobs.exceptions import JobNotFoundError
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .schemas import (
    DocumentDeleteRequest,
    DocumentMetadataUpdateRequest,
    DocumentRecord,
)
from .service import DocumentUploadPayload, DocumentsService
from ..users.models import UserRole


router = APIRouter(tags=["documents"])


@cbv(router)
class DocumentsRoutes:
    session: AsyncSession = Depends(get_session)
    selection: WorkspaceContext = Depends(bind_workspace_context)
    service: DocumentsService = Depends(get_documents_service)
    events_service: EventsService = Depends(get_events_service)


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

    @router.get(
        "/documents/{document_id}/events",
        response_model=list[EventRecord],
        status_code=status.HTTP_200_OK,
        summary="List events recorded for a document",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:documents:read"}, require_workspace=True)
    async def list_document_events(
        self,
        document_id: str,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> list[EventRecord]:
        try:
            await self.service.get_document(
                document_id=document_id,
                include_deleted=True,
                emit_event=False,
            )
        except DocumentNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        events = await self.events_service.list_document_events(
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
        return events


@router.patch(
    "/documents/{document_id}",
    response_model=DocumentRecord,
    status_code=status.HTTP_200_OK,
    summary="Update document metadata for the active workspace",
    response_model_exclude_none=True,
)
async def update_document_metadata(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    selection: WorkspaceContext = Depends(bind_workspace_context),
    service: DocumentsService = Depends(get_documents_service),
) -> DocumentRecord:
    del session  # request-scoped dependency; session is bound via request.state
    del selection  # ensure workspace context dependency runs

    user = service.current_user
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if getattr(user, "role", None) != UserRole.ADMIN:
        workspace = service.current_workspace
        if workspace is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Workspace context required")

        required = {"workspace:documents:write"}
        if not required.issubset(service.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    raw_body = await request.body()
    payload_data: dict[str, Any] | None = None
    if raw_body:
        try:
            payload_data = json.loads(raw_body)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive parsing
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body") from exc
    payload = DocumentMetadataUpdateRequest.model_validate(payload_data or {})

    try:
        record = await service.update_document_metadata(
            document_id=document_id,
            metadata=payload.metadata,
            event_type=payload.event_type,
            event_payload=payload.event_payload,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return record


@router.get(
    "/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download the original uploaded document",
    response_class=FileResponse,
)
async def download_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    selection: WorkspaceContext = Depends(bind_workspace_context),
    service: DocumentsService = Depends(get_documents_service),
) -> FileResponse:
    del session  # request-scoped dependency; session is bound via request.state
    del selection  # ensure workspace context dependency runs

    user = service.current_user
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if getattr(user, "role", None) != UserRole.ADMIN:
        workspace = service.current_workspace
        if workspace is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Workspace context required")

        required = {"workspace:documents:read"}
        if not required.issubset(service.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        download = await service.prepare_document_download(document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        detail = {"error": "document_file_missing", "message": str(exc)}
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc

    headers = {
        "X-Document-ID": download.document_id,
        "X-Document-SHA256": download.sha256,
    }
    media_type = download.content_type or "application/octet-stream"

    return FileResponse(
        download.path,
        media_type=media_type,
        filename=download.filename,
        headers=headers,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DocumentRecord,
    status_code=status.HTTP_200_OK,
    summary="Soft delete a document from the active workspace",
    response_model_exclude_none=True,
)
async def delete_document(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    selection: WorkspaceContext = Depends(bind_workspace_context),
    service: DocumentsService = Depends(get_documents_service),
) -> DocumentRecord:
    del session  # request-scoped dependency; session is bound via request.state
    del selection  # ensure workspace context dependency runs

    user = service.current_user
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if getattr(user, "role", None) != UserRole.ADMIN:
        workspace = service.current_workspace
        if workspace is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Workspace context required")

        required = {"workspace:documents:write"}
        if not required.issubset(service.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    raw_body = await request.body()
    payload_data: dict[str, Any] | None = None
    if raw_body:
        try:
            payload_data = json.loads(raw_body)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive parsing
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body") from exc
    delete_request = DocumentDeleteRequest.model_validate(payload_data or {})
    reason = delete_request.reason

    try:
        record = await service.delete_document(document_id=document_id, reason=reason)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return record


@router.post(
    "/documents",
    response_model=DocumentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to the active workspace",
    response_model_exclude_none=True,
)
async def upload_document(
    file: UploadFile = File(...),
    expires_at: str | None = Form(None),
    produced_by_job_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    selection: WorkspaceContext = Depends(bind_workspace_context),
    service: DocumentsService = Depends(get_documents_service),
) -> DocumentRecord:
    del session  # request-scoped dependency; session is bound via request.state
    del selection  # ensure workspace context dependency runs

    user = service.current_user
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if getattr(user, "role", None) != UserRole.ADMIN:
        workspace = service.current_workspace
        if workspace is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Workspace context required")

        required = {"workspace:documents:write"}
        if not required.issubset(service.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        await file.seek(0)
        record = await service.create_document(
            upload=DocumentUploadPayload(
                filename=file.filename,
                content_type=file.content_type,
                stream=file.file,
            ),
            expires_at=expires_at,
            produced_by_job_id=produced_by_job_id,
        )
    except DocumentTooLargeError as exc:
        detail = {
            "error": "document_too_large",
            "message": str(exc),
            "max_upload_bytes": exc.limit,
            "received_bytes": exc.received,
        }
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=detail,
        ) from exc
    except InvalidDocumentExpirationError as exc:
        detail = {"error": "invalid_expiration", "message": str(exc)}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except JobNotFoundError as exc:
        detail = {"error": "invalid_job_reference", "message": str(exc)}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    finally:
        await file.close()

    return record


__all__ = ["router"]
