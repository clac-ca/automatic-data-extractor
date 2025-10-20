"""Exception stubs for the documents module rewrite."""

from __future__ import annotations


class DocumentNotFoundError(Exception):
    """Raised when a document lookup does not yield a result."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document {document_id!r} not found")
        self.document_id = document_id


class DocumentFileMissingError(Exception):
    """Raised when a stored document file cannot be located on disk."""

    def __init__(self, *, document_id: str, stored_uri: str) -> None:
        message = (
            f"Stored file for document {document_id!r} was not found at {stored_uri!r}."
        )
        super().__init__(message)
        self.document_id = document_id
        self.stored_uri = stored_uri


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
    "DocumentFileMissingError",
    "DocumentTooLargeError",
    "InvalidDocumentExpirationError",
]
