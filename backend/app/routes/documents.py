"""HTTP endpoints for document ingestion and retrieval."""

from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document
from ..schemas import DocumentResponse
from ..services.documents import (
    DocumentNotFoundError,
    get_document as get_document_service,
    iter_document_file,
    list_documents as list_documents_service,
    resolve_document_path,
    store_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])

_DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(document)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
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
        )
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


def _download_iterator(document: Document) -> Iterator[bytes]:
    return iter_document_file(document, chunk_size=_DOWNLOAD_CHUNK_SIZE)


@router.get("/{document_id}/download")
def download_document(
    document_id: str, db: Session = Depends(get_db)
) -> StreamingResponse:
    """Stream the stored file for download."""

    try:
        document = get_document_service(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    path = resolve_document_path(document)
    if not path.exists():
        msg = f"Stored file for document '{document_id}' is missing"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    headers = {
        "Content-Disposition": f"attachment; filename=\"{document.original_filename}\""
    }
    media_type = document.content_type or "application/octet-stream"
    return StreamingResponse(
        _download_iterator(document),
        media_type=media_type,
        headers=headers,
    )


__all__ = ["router"]
