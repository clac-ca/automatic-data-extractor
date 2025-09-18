"""HTTP endpoints for document ingestion and retrieval."""

from __future__ import annotations

from datetime import datetime
import logging
import os
import unicodedata
from urllib.parse import quote
from typing import Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import AuditEvent, Document
from ..schemas import (
    AuditEventListResponse,
    AuditEventResponse,
    DocumentDeleteRequest,
    DocumentResponse,
)
from ..services.audit_log import list_entity_events
from ..services.documents import (
    DocumentNotFoundError,
    DocumentStoragePathError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
    delete_document as delete_document_service,
    get_document as get_document_service,
    iter_document_file,
    list_documents as list_documents_service,
    resolve_document_path,
    store_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])

_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_DEFAULT_DOWNLOAD_FILENAME = "downloaded-document"


logger = logging.getLogger(__name__)


def _ascii_filename_fallback(filename: str) -> str:
    """Return an ASCII-only filename suitable for HTTP headers."""

    stem, ext = os.path.splitext(filename)

    def _normalise(component: str) -> str:
        normalised = unicodedata.normalize("NFKD", component)
        ascii_component = normalised.encode("ascii", "ignore").decode("ascii")
        ascii_component = ascii_component.replace("\r", " ").replace("\n", " ")
        ascii_component = ascii_component.replace('"', "'")
        ascii_component = " ".join(ascii_component.split())
        return ascii_component.strip()

    ascii_stem = _normalise(stem)
    ascii_ext = _normalise(ext)

    # Only keep the extension if it's not empty and not just a dot
    if ascii_ext and ascii_ext != ".":
        if not ascii_ext.startswith("."):
            ascii_ext = f".{ascii_ext}"
    else:
        ascii_ext = ""

    if not ascii_stem:
        ascii_stem = _DEFAULT_DOWNLOAD_FILENAME

    return f"{ascii_stem}{ascii_ext}"


def _content_disposition(filename: str | None) -> str:
    """Generate a Content-Disposition header that supports UTF-8 filenames."""

    if not filename:
        return "attachment"

    sanitised = (
        filename.replace("\r", " ")
        .replace("\n", " ")
        .replace('"', "'")
        .strip()
    )

    if not all(ord(c) <= 255 for c in sanitised):
        ascii_filename = _ascii_filename_fallback(filename)
        encoded = quote(filename, safe="")
        header = f'attachment; filename="{ascii_filename}"'
        if encoded:
            header += f"; filename*=utf-8''{encoded}"
        return header

    if not sanitised:
        ascii_filename = _ascii_filename_fallback(filename)
        return f'attachment; filename="{ascii_filename}"'

    return f'attachment; filename="{sanitised}"'


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(document)


def _audit_to_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse.model_validate(event)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    expires_at: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Ingest an uploaded document and return canonical metadata."""

    try:
        await file.seek(0)
        document = store_document(
            db,
            original_filename=file.filename,
            content_type=file.content_type,
            data=file.file,
            expires_at=expires_at,
        )
    except DocumentTooLargeError as exc:
        detail = {
            "error": "document_too_large",
            "message": str(exc),
            "max_upload_bytes": exc.limit,
            "received_bytes": exc.received,
        }
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=detail,
        ) from exc
    except InvalidDocumentExpirationError as exc:
        detail = {
            "error": "invalid_expiration",
            "message": str(exc),
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    finally:
        await file.close()
    return _to_response(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    """Return stored documents ordered by recency."""

    documents = list_documents_service(db)
    return [_to_response(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str, db: Session = Depends(get_db)
) -> DocumentResponse:
    """Return metadata for a single document."""

    try:
        document = get_document_service(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(document)


def _download_iterator(
    document: Document, *, settings: config.Settings | None = None
) -> Iterator[bytes]:
    return iter_document_file(
        document,
        settings=settings,
        chunk_size=_DOWNLOAD_CHUNK_SIZE,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: str, db: Session = Depends(get_db)
) -> StreamingResponse:
    """Stream the stored file for download."""

    try:
        document = get_document_service(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    settings = config.get_settings()
    try:
        path = resolve_document_path(document, settings=settings)
    except DocumentStoragePathError as exc:
        logger.exception(
            "Document stored URI resolves outside documents directory",
            extra={
                "document_id": document.document_id,
                "stored_uri": document.stored_uri,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored document path is invalid",
        ) from exc

    if not path.exists() or not path.is_file():
        msg = f"Stored file for document '{document_id}' is missing"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    headers = {"Content-Disposition": _content_disposition(document.original_filename)}
    media_type = document.content_type or "application/octet-stream"
    return StreamingResponse(
        _download_iterator(document, settings=settings),
        media_type=media_type,
        headers=headers,
    )


@router.delete("/{document_id}", response_model=DocumentResponse)
def delete_document(
    document_id: str,
    payload: DocumentDeleteRequest,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Soft delete a stored document and remove its bytes from disk."""

    try:
        document = delete_document_service(
            db,
            document_id,
            deleted_by=payload.deleted_by,
            delete_reason=payload.delete_reason,
            audit_actor_type="user",
            audit_actor_label=payload.deleted_by,
            audit_source="api",
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(document)


@router.get("/{document_id}/audit-events", response_model=AuditEventListResponse)
def list_document_audit_events(
    document_id: str,
    db: Session = Depends(get_db),
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    request_id: str | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
) -> AuditEventListResponse:
    try:
        get_document_service(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        result = list_entity_events(
            db,
            entity_type="document",
            entity_id=document_id,
            limit=limit,
            offset=offset,
            event_type=event_type,
            source=source,
            request_id=request_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [_audit_to_response(event) for event in result.events]
    return AuditEventListResponse(
        items=items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


__all__ = ["router"]
