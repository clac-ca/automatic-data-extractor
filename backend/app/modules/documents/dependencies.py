"""FastAPI dependencies for the documents module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import DocumentsService


get_documents_service = service_dependency(DocumentsService)


__all__ = ["get_documents_service"]
