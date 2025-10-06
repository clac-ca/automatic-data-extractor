import json
from typing import Annotated, Any

from fastapi import (
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

from app.core.schema import ErrorMessage

from ..auth.security import access_control
from ..workspaces.dependencies import require_workspace_context
from ..workspaces.routing import workspace_scoped_router
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

router = workspace_scoped_router(tags=["documents"])

WorkspaceContextDep = Annotated[WorkspaceContext, Depends(require_workspace_context)]
DocumentsReadServiceDep = Annotated[
    DocumentsService,
    Depends(
        access_control(
            permissions={"workspace:documents:read"},
            require_workspace=True,
            service_dependency=get_documents_service,
        )
    ),
]
DocumentsWriteServiceDep = Annotated[
    DocumentsService,
    Depends(
        access_control(
            permissions={"workspace:documents:write"},
            require_workspace=True,
            service_dependency=get_documents_service,
        )
    ),
]


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


@router.post(
    "/documents",
    response_model=DocumentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Metadata payload or expiration timestamp is invalid.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to upload documents.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document uploads.",
            "model": ErrorMessage,
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "description": "Uploaded file exceeds the configured size limit.",
            "model": ErrorMessage,
        },
    },
)
async def upload_document(
    _: WorkspaceContextDep,
    service: DocumentsWriteServiceDep,
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
    expires_at: Annotated[str | None, Form()] = None,
) -> DocumentRecord:
    payload = _parse_metadata(metadata)
    try:
        return await service.create_document(
            upload=file,
            metadata=payload,
            expires_at=expires_at,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except InvalidDocumentExpirationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/documents",
    response_model=list[DocumentRecord],
    status_code=status.HTTP_200_OK,
    summary="List documents",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list documents.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
            "model": ErrorMessage,
        },
    },
)
async def list_documents(
    _: WorkspaceContextDep,
    service: DocumentsReadServiceDep,
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DocumentRecord]:
    return await service.list_documents(limit=limit, offset=offset)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access documents.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def read_document(
    document_id: str,
    _: WorkspaceContextDep,
    service: DocumentsReadServiceDep,
) -> DocumentRecord:
    try:
        return await service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/documents/{document_id}/download",
    summary="Download a stored document",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to download documents.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document downloads.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document is missing or its stored file is unavailable.",
            "model": ErrorMessage,
        },
    },
)
async def download_document(
    document_id: str,
    _: WorkspaceContextDep,
    service: DocumentsReadServiceDep,
) -> StreamingResponse:
    try:
        record, stream = await service.stream_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = record.content_type or "application/octet-stream"
    filename = record.original_filename.replace('"', "")
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a document",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete documents.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document deletion.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def delete_document(
    document_id: str,
    _: WorkspaceContextDep,
    service: DocumentsWriteServiceDep,
    *,
    payload: Annotated[DocumentDeleteRequest | None, Body()] = None,
) -> None:
    try:
        await service.delete_document(
            document_id=document_id,
            reason=payload.reason if payload else None,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
