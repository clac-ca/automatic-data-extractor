"""HTTP endpoints for document ingestion and retrieval."""

from __future__ import annotations

from datetime import datetime
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
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
    list_documents as list_documents_service,
    resolve_document_path,
    store_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


logger = logging.getLogger(__name__)
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


@router.get("/{document_id}/download")
def download_document(
    document_id: str, db: Session = Depends(get_db)
) -> FileResponse:
    """Return the stored file for download."""

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

    try:
        with path.open("rb"):
            pass
    except FileNotFoundError as exc:
        msg = f"Stored file for document '{document_id}' is missing"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
    except OSError as exc:  # pragma: no cover - unexpected I/O failure
        logger.exception(
            "Failed to open stored file for download",
            extra={
                "document_id": document.document_id,
                "stored_uri": document.stored_uri,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to read stored document bytes",
        ) from exc

    media_type = document.content_type or "application/octet-stream"
    response = FileResponse(
        path,
        media_type=media_type,
        filename=document.original_filename,
    )
    return response


@router.delete("/{document_id}", response_model=DocumentResponse)
def delete_document(
    document_id: str,
    payload: DocumentDeleteRequest,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Soft delete a stored document and remove its bytes from disk."""

    try:
        result = delete_document_service(
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
    return _to_response(result.document)


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
