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
    """Raised when a stored document file cannot be located."""

    def __init__(
        self,
        *,
        document_id: UUID | str,
        blob_name: str,
        version_id: str | None = None,
    ) -> None:
        doc_id = str(document_id)
        details = f"Stored file for document {doc_id!r} was not found at {blob_name!r}."
        if version_id:
            details = f"{details} (version {version_id!r})"
        super().__init__(details)
        self.document_id = doc_id
        self.blob_name = blob_name
        self.version_id = version_id


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


class DocumentWorksheetParseError(Exception):
    """Raised when worksheet metadata cannot be read from a workbook."""

    def __init__(
        self, *, document_id: UUID | str, blob_name: str, reason: str | None = None
    ) -> None:
        doc_id = str(document_id)
        details = " Unable to read worksheet metadata."
        if reason:
            details = f" Parse failed ({reason})."

        message = f"Worksheet inspection failed for document {doc_id!r} at {blob_name!r}.{details}"

        super().__init__(message)
        self.document_id = doc_id
        self.blob_name = blob_name
        self.reason = reason


class DocumentPreviewUnsupportedError(Exception):
    """Raised when a document preview is requested for an unsupported file type."""

    def __init__(self, *, document_id: UUID | str, file_type: str) -> None:
        doc_id = str(document_id)
        message = f"Preview is not supported for document {doc_id!r} with file type {file_type!r}."
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
        self, *, document_id: UUID | str, blob_name: str, reason: str | None = None
    ) -> None:
        doc_id = str(document_id)
        details = " Unable to generate document preview."
        if reason:
            details = f" Preview generation failed ({reason})."
        message = f"Preview generation failed for document {doc_id!r} at {blob_name!r}.{details}"
        super().__init__(message)
        self.document_id = doc_id
        self.blob_name = blob_name
        self.reason = reason


class DocumentNameConflictError(Exception):
    """Raised when a document upload collides with an existing name."""

    def __init__(self, *, document_id: UUID | str, name: str) -> None:
        doc_id = str(document_id)
        message = f"Document name {name!r} is already in use (document {doc_id!r})."
        super().__init__(message)
        self.document_id = doc_id
        self.name = name


class DocumentRestoreNameConflictError(Exception):
    """Raised when restoring a document would collide with an active document name."""

    def __init__(
        self,
        *,
        document_id: UUID | str,
        name: str,
        conflicting_document_id: UUID | str,
        conflicting_name: str,
        suggested_name: str,
    ) -> None:
        doc_id = str(document_id)
        conflicting_id = str(conflicting_document_id)
        message = (
            f"Cannot restore document {doc_id!r} as {name!r}; "
            f"active document {conflicting_id!r} already uses {conflicting_name!r}."
        )
        super().__init__(message)
        self.document_id = doc_id
        self.name = name
        self.conflicting_document_id = conflicting_id
        self.conflicting_name = conflicting_name
        self.suggested_name = suggested_name


class InvalidDocumentRenameError(Exception):
    """Raised when a rename request violates filename rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DocumentVersionNotFoundError(Exception):
    """Raised when a requested document version does not exist."""

    def __init__(self, *, document_id: UUID | str, version_no: int) -> None:
        doc_id = str(document_id)
        message = f"Document {doc_id!r} has no version {version_no}."
        super().__init__(message)
        self.document_id = doc_id
        self.version_no = version_no


class InvalidDocumentTagsError(Exception):
    """Raised when document tag inputs fail validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidDocumentCommentMentionsError(Exception):
    """Raised when document comment mentions are invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DocumentViewNotFoundError(Exception):
    """Raised when a document view cannot be found or is not visible."""

    def __init__(self, view_id: UUID | str) -> None:
        identifier = str(view_id)
        super().__init__(f"Document view {identifier!r} not found")
        self.view_id = identifier


class DocumentViewConflictError(Exception):
    """Raised when a document view collides with an existing name or key."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DocumentViewImmutableError(Exception):
    """Raised when attempting to mutate a system document view."""

    def __init__(self, message: str = "System views cannot be modified.") -> None:
        super().__init__(message)


__all__ = [
    "DocumentNotFoundError",
    "DocumentFileMissingError",
    "DocumentTooLargeError",
    "DocumentWorksheetParseError",
    "DocumentPreviewUnsupportedError",
    "DocumentPreviewSheetNotFoundError",
    "DocumentPreviewParseError",
    "DocumentNameConflictError",
    "DocumentRestoreNameConflictError",
    "InvalidDocumentRenameError",
    "DocumentVersionNotFoundError",
    "InvalidDocumentTagsError",
    "InvalidDocumentCommentMentionsError",
    "DocumentViewNotFoundError",
    "DocumentViewConflictError",
    "DocumentViewImmutableError",
]
