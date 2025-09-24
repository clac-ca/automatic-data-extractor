"""Module-specific exceptions for document workflows."""

from __future__ import annotations


class DocumentNotFoundError(Exception):
    """Raised when a document lookup does not yield a result."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document {document_id!r} not found")
        self.document_id = document_id


class DocumentTooLargeError(Exception):
    """Raised when an uploaded document exceeds the configured size limit."""

    def __init__(self, *, limit: int, received: int) -> None:
        message = (
            f"Uploaded file is {received:,} bytes which exceeds the allowed "
            f"maximum of {limit:,} bytes."
        )
        super().__init__(message)
        self.limit = limit
        self.received = received


class InvalidDocumentExpirationError(Exception):
    """Raised when an ``expires_at`` override cannot be parsed or is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = [
    "DocumentNotFoundError",
    "DocumentTooLargeError",
    "InvalidDocumentExpirationError",
]
