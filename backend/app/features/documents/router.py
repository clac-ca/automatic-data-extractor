from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from pydantic import ValidationError

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.pagination.dependencies import get_pagination_params
from backend.app.features.roles.dependencies import require_workspace
from backend.app.shared.core.errors import ProblemDetail, ProblemException
from backend.app.shared.core.pagination import PaginationParams
from backend.app.shared.core.schema import ErrorMessage

from ..users.models import User
from .dependencies import get_documents_service
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .filtering import DocumentFilterParams
from .schemas import DocumentListResponse, DocumentRecord
from .service import DocumentsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)


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


def _build_download_disposition(filename: str) -> str:
    """Return a safe Content-Disposition header value for ``filename``."""

    stripped = filename.strip()
    cleaned = "".join(
        ch for ch in stripped if unicodedata.category(ch)[0] != "C"
    ).strip()
    candidate = cleaned or "download"

    fallback_chars: list[str] = []
    for char in candidate:
        code_point = ord(char)
        if 32 <= code_point < 127 and char not in {'"', "\\", ";", ":"}:
            fallback_chars.append(char)
        else:
            fallback_chars.append("_")
    fallback = "".join(fallback_chars).strip("_ ") or "download"
    fallback = fallback[:255]

    encoded = quote(candidate, safe="")
    if fallback == candidate:
        return f'attachment; filename="{fallback}"'

    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def _parse_document_filters(
    request: Request,
    *,
    status_values: list[str] | None,
    source: list[str] | None,
    tag: list[str] | None,
    uploader: str | None,
    uploader_ids: list[str] | None,
    q: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    last_run_from: datetime | None,
    last_run_to: datetime | None,
    byte_size_min: int | None,
    byte_size_max: int | None,
    sort: str | None,
) -> DocumentFilterParams:
    allowed_filter_keys = {
        "status",
        "source",
        "tag",
        "uploader",
        "uploader_id",
        "q",
        "created_from",
        "created_to",
        "last_run_from",
        "last_run_to",
        "byte_size_min",
        "byte_size_max",
        "sort",
    }
    allowed_query_keys = allowed_filter_keys | {"page", "per_page", "include_total"}

    for key in request.query_params.keys():
        if key not in allowed_query_keys:
            message = f"Unknown query parameter: {key}"
            raise ProblemException(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Invalid query parameter",
                detail=message,
                errors={key: ["Unknown query parameter"]},
            )

    raw = {
        "status": status_values or [],
        "source": source or [],
        "tags": tag or [],
        "uploader": uploader,
        "uploader_ids": uploader_ids or [],
        "q": q,
        "created_from": created_from,
        "created_to": created_to,
        "last_run_from": last_run_from,
        "last_run_to": last_run_to,
        "byte_size_min": byte_size_min,
        "byte_size_max": byte_size_max,
        "sort": sort,
    }

    try:
        return DocumentFilterParams.model_validate(raw)
    except ValidationError as exc:
        errors: dict[str, list[str]] = {}
        for error in exc.errors():
            loc = error.get("loc", ())
            field = str(loc[0]) if loc else "query"
            errors.setdefault(field, []).append(error.get("msg", "Invalid value"))
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid query parameters",
            detail="One or more query parameters are invalid.",
            errors=errors or None,
        ) from exc


@router.post(
    "/documents",
    dependencies=[Security(require_csrf)],
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
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
    expires_at: Annotated[str | None, Form()] = None,
) -> DocumentRecord:
    payload = _parse_metadata(metadata)
    try:
        return await service.create_document(
            workspace_id=workspace_id,
            upload=file,
            metadata=payload,
            expires_at=expires_at,
            actor=_actor,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except InvalidDocumentExpirationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/documents",
    response_model=DocumentListResponse,
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
        status.HTTP_400_BAD_REQUEST: {
            "description": "Query parameters are invalid or unsupported.",
            "model": ProblemDetail,
        },
    },
)
async def list_documents(
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    request: Request,
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    status: Annotated[
        list[str] | None,
        Query(
            description="Filter by one or more document statuses.",
            example=["uploaded", "processed"],
        ),
    ] = None,
    source: Annotated[
        list[str] | None,
        Query(
            description="Restrict results to the given document sources.",
            example=["manual_upload"],
        ),
    ] = None,
    tag: Annotated[
        list[str] | None,
        Query(
            description="Return documents containing any of the provided tags.",
            example=["finance", "2024"],
        ),
    ] = None,
    uploader: Annotated[
        str | None,
        Query(
            description="Identity shortcut; use `me` to resolve to the authenticated uploader.",
            example="me",
        ),
    ] = None,
    uploader_id: Annotated[
        list[str] | None,
        Query(
            description="Filter by explicit uploader ULIDs (repeatable).",
            example=["01H0H0H0H0H0H0H0H0H0H0H0H"],
        ),
    ] = None,
    q: Annotated[
        str | None,
        Query(
            description="Substring search applied to document name or uploader metadata.",
            example="quarterly",
        ),
    ] = None,
    created_from: Annotated[
        datetime | None,
        Query(
            description="Return documents created on/after this UTC timestamp.",
            example="2024-01-01T00:00:00Z",
        ),
    ] = None,
    created_to: Annotated[
        datetime | None,
        Query(
            description="Return documents created on/before this UTC timestamp.",
            example="2024-01-31T23:59:59Z",
        ),
    ] = None,
    last_run_from: Annotated[
        datetime | None,
        Query(
            description="Return documents with a last run on/after this UTC timestamp.",
            example="2024-02-01T00:00:00Z",
        ),
    ] = None,
    last_run_to: Annotated[
        datetime | None,
        Query(
            description="Return documents with a last run on/before this UTC timestamp (inclusive).",
            example="2024-02-29T23:59:59Z",
        ),
    ] = None,
    byte_size_min: Annotated[
        int | None,
        Query(
            ge=0,
            description="Only include documents at least this many bytes in size.",
            example=1024,
        ),
    ] = None,
    byte_size_max: Annotated[
        int | None,
        Query(
            ge=0,
            description="Only include documents at most this many bytes in size.",
            example=1048576,
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Single-field sort directive (prefix with '-' for descending).",
            example="-created_at",
        ),
    ] = None,
) -> DocumentListResponse:
    filters = _parse_document_filters(
        request,
        status_values=status,
        source=source,
        tag=tag,
        uploader=uploader,
        uploader_ids=uploader_id,
        q=q,
        created_from=created_from,
        created_to=created_to,
        last_run_from=last_run_from,
        last_run_to=last_run_to,
        byte_size_min=byte_size_min,
        byte_size_max=byte_size_max,
        sort=sort,
    )
    return await service.list_documents(
        workspace_id=workspace_id,
        page=pagination.page,
        per_page=pagination.per_page,
        include_total=pagination.include_total,
        filters=filters.to_filters(),
        sort=filters.sort,
        actor=_actor,
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
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> DocumentRecord:
    try:
        return await service.get_document(
            workspace_id=workspace_id,
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
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> StreamingResponse:
    try:
        record, stream = await service.stream_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = record.content_type or "application/octet-stream"
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = _build_download_disposition(record.original_filename)
    return response


@router.delete(
    "/documents/{document_id}",
    dependencies=[Security(require_csrf)],
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
    workspace_id: Annotated[
        str, Path(min_length=1, description="Workspace identifier")
    ],
    document_id: Annotated[
        str, Path(min_length=1, description="Document identifier")
    ],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.delete_document(
            workspace_id=workspace_id,
            document_id=document_id,
            actor=actor,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
