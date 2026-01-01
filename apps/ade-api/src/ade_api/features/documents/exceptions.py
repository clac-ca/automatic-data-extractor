"""Exception stubs for the documents module rewrite."""

from __future__ import annotations

from uuid import UUID


class DocumentNotFoundError(Exception):
    """Raised when a document lookup does not yield a result."""

    def __init__(self, document_id: UUID | str) -> None:
        doc_id = str(document_id)
        super().__init__(f"Document {doc_id!r} not found")
        self.document_id = doc_id


class DocumentFileMissingError(Exception):
    """Raised when a stored document file cannot be located on disk."""

    def __init__(self, *, document_id: UUID | str, stored_uri: str) -> None:
        doc_id = str(document_id)
        message = f"Stored file for document {doc_id!r} was not found at {stored_uri!r}."
        super().__init__(message)
        self.document_id = doc_id
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


class DocumentWorksheetParseError(Exception):
    """Raised when worksheet metadata cannot be read from a workbook."""

    def __init__(
        self, *, document_id: UUID | str, stored_uri: str, reason: str | None = None
    ) -> None:
        doc_id = str(document_id)
        details = " Unable to read worksheet metadata."
        if reason:
            details = f" Parse failed ({reason})."

        message = (
            f"Worksheet inspection failed for document {doc_id!r} at {stored_uri!r}.{details}"
        )

        super().__init__(message)
        self.document_id = doc_id
        self.stored_uri = stored_uri
        self.reason = reason


class DocumentPreviewUnsupportedError(Exception):
    """Raised when a document preview is requested for an unsupported file type."""

    def __init__(self, *, document_id: UUID | str, file_type: str) -> None:
        doc_id = str(document_id)
        message = (
            f"Preview is not supported for document {doc_id!r} with file type {file_type!r}."
        )
        super().__init__(message)
        self.document_id = doc_id
        self.file_type = file_type


class DocumentPreviewSheetNotFoundError(Exception):
    """Raised when a requested worksheet is not present in the document."""

    def __init__(self, *, document_id: UUID | str, sheet: str) -> None:
        doc_id = str(document_id)
        message = f"Sheet {sheet!r} was not found in document {doc_id!r}."
        super().__init__(message)
        self.document_id = doc_id
        self.sheet = sheet


class DocumentPreviewParseError(Exception):
    """Raised when a document preview cannot be generated."""

    def __init__(
        self, *, document_id: UUID | str, stored_uri: str, reason: str | None = None
    ) -> None:
        doc_id = str(document_id)
        details = " Unable to generate document preview."
        if reason:
            details = f" Preview generation failed ({reason})."
        message = (
            f"Preview generation failed for document {doc_id!r} at {stored_uri!r}.{details}"
        )
        super().__init__(message)
        self.document_id = doc_id
        self.stored_uri = stored_uri
        self.reason = reason


class InvalidDocumentTagsError(Exception):
    """Raised when document tag inputs fail validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DocumentUploadSessionNotFoundError(Exception):
    """Raised when an upload session cannot be located."""

    def __init__(self, session_id: UUID | str) -> None:
        session_value = str(session_id)
        super().__init__(f"Upload session {session_value!r} not found")
        self.session_id = session_value


class DocumentUploadSessionExpiredError(Exception):
    """Raised when an upload session has expired."""

    def __init__(self, session_id: UUID | str) -> None:
        session_value = str(session_id)
        super().__init__(f"Upload session {session_value!r} has expired")
        self.session_id = session_value


class DocumentUploadRangeError(Exception):
    """Raised when an upload range is invalid for the session."""

    def __init__(self, message: str, *, next_expected_ranges: list[str]) -> None:
        super().__init__(message)
        self.next_expected_ranges = next_expected_ranges


class DocumentUploadSessionNotReadyError(Exception):
    """Raised when attempting to commit before an upload completes."""

    def __init__(self, session_id: UUID | str) -> None:
        session_value = str(session_id)
        super().__init__(f"Upload session {session_value!r} is not complete")
        self.session_id = session_value


__all__ = [
    "DocumentNotFoundError",
    "DocumentFileMissingError",
    "DocumentTooLargeError",
    "InvalidDocumentExpirationError",
    "DocumentWorksheetParseError",
    "DocumentPreviewUnsupportedError",
    "DocumentPreviewSheetNotFoundError",
    "DocumentPreviewParseError",
    "InvalidDocumentTagsError",
    "DocumentUploadRangeError",
    "DocumentUploadSessionExpiredError",
    "DocumentUploadSessionNotFoundError",
    "DocumentUploadSessionNotReadyError",
]
