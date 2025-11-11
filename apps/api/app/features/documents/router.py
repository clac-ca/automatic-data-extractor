from __future__ import annotations

import json
import unicodedata
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from apps.api.app.shared.core.errors import ProblemDetail
from apps.api.app.shared.core.errors import ProblemDetail
from apps.api.app.shared.dependency import (
    get_documents_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)
from apps.api.app.shared.pagination import PageParams
from apps.api.app.shared.sorting import make_sort_dependency
from apps.api.app.shared.types import OrderBy

from ..users.models import User
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .filters import DocumentFilters
from .schemas import DocumentOut, DocumentPage
from .service import DocumentsService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)


get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)

_FILTER_KEYS = {
    "q",
    "status_in",
    "source_in",
    "tags_in",
    "uploader",
    "uploader_id_in",
    "created_at_from",
    "created_at_to",
    "last_run_from",
    "last_run_to",
    "byte_size_from",
    "byte_size_to",
}


def get_document_filters(request: Request) -> DocumentFilters:
    allowed = _FILTER_KEYS
    allowed_with_shared = allowed | {"sort", "page", "page_size", "include_total"}
    extras = sorted(
        {key for key in request.query_params.keys() if key not in allowed_with_shared}
    )
    if extras:
        detail = [
            {
                "type": "extra_forbidden",
                "loc": ["query", key],
                "msg": "Extra inputs are not permitted",
                "input": request.query_params.get(key),
            }
            for key in extras
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    raw: dict[str, Any] = {}
    for key in allowed:
        values = request.query_params.getlist(key)
        if not values:
            continue
        raw[key] = values if len(values) > 1 else values[0]
    return DocumentFilters.model_validate(raw)


def _parse_metadata(metadata: str | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    candidate = metadata.strip()
    if not candidate:
        return {}
    try:
        decoded = json.loads(candidate)
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


@router.post(
    "/documents",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Metadata payload or expiration timestamp is invalid.",
            "model": ProblemDetail,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to upload documents.",
            "model": ProblemDetail,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document uploads.",
            "model": ProblemDetail,
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "description": "Uploaded file exceeds the configured size limit.",
            "model": ProblemDetail,
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
) -> DocumentOut:
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
    response_model=DocumentPage,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list documents.",
            "model": ProblemDetail,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
            "model": ProblemDetail,
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
    page: Annotated[PageParams, Depends()],
    filters: Annotated[DocumentFilters, Depends(get_document_filters)],
    order_by: Annotated[OrderBy, Depends(get_sort_order)],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Documents.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> DocumentPage:
    return await service.list_documents(
        workspace_id=workspace_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
        order_by=order_by,
        filters=filters,
        actor=actor,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access documents.",
            "model": ProblemDetail,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
            "model": ProblemDetail,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
            "model": ProblemDetail,
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
) -> DocumentOut:
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
            "model": ProblemDetail,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document downloads.",
            "model": ProblemDetail,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document is missing or its stored file is unavailable.",
            "model": ProblemDetail,
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
            "model": ProblemDetail,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document deletion.",
            "model": ProblemDetail,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
            "model": ProblemDetail,
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
