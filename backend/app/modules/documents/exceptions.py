"""Module-specific exceptions for document workflows."""

from __future__ import annotations


class DocumentNotFoundError(Exception):
    """Raised when a document lookup does not yield a result."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document {document_id!r} not found")
        self.document_id = document_id


__all__ = ["DocumentNotFoundError"]
