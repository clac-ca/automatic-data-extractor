from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_app_settings
from app.core.config import Settings
from app.core.schema import ErrorMessage
from app.db.session import get_session

from ..auth.dependencies import bind_current_user
from ..users.models import User
from ..workspaces.dependencies import require_workspace_access
from ..workspaces.schemas import WorkspaceProfile
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .schemas import DocumentRecord
from .service import DocumentsService

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["documents"])


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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Documents.ReadWrite"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
    expires_at: Annotated[str | None, Form()] = None,
) -> DocumentRecord:
    service = DocumentsService(session=session, settings=settings)
    payload = _parse_metadata(metadata)
    try:
        return await service.create_document(
            workspace_id=workspace.workspace_id,
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
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Documents.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DocumentRecord]:
    service = DocumentsService(session=session, settings=settings)
    return await service.list_documents(
        workspace_id=workspace.workspace_id, limit=limit, offset=offset
    )


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
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Documents.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> DocumentRecord:
    service = DocumentsService(session=session, settings=settings)
    try:
        return await service.get_document(
            workspace_id=workspace.workspace_id,
            document_id=document_id,
        )
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
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Documents.Read"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> StreamingResponse:
    service = DocumentsService(session=session, settings=settings)
    try:
        record, stream = await service.stream_document(
            workspace_id=workspace.workspace_id,
            document_id=document_id,
        )
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
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    workspace: Annotated[
        WorkspaceProfile,
        Security(
            require_workspace_access,
            scopes=["Workspace.Read", "Workspace.Documents.ReadWrite"],
        ),
    ],
    current_user: Annotated[User, Depends(bind_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> None:
    service = DocumentsService(session=session, settings=settings)
    try:
        await service.delete_document(
            workspace_id=workspace.workspace_id,
            document_id=document_id,
            actor=current_user,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
