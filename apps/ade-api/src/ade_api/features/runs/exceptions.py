"""Domain exceptions for the runs feature."""

from __future__ import annotations

__all__ = [
    "RunNotFoundError",
    "RunDocumentMissingError",
    "RunLogsFileMissingError",
    "RunOutputMissingError",
    "RunOutputNotReadyError",
    "RunOutputPreviewUnsupportedError",
    "RunOutputPreviewSheetNotFoundError",
    "RunOutputPreviewParseError",
    "RunOutputSheetUnsupportedError",
    "RunOutputSheetParseError",
    "RunInputMissingError",
    "RunQueueFullError",
]


class RunNotFoundError(RuntimeError):
    """Raised when a requested run row cannot be located."""


class RunDocumentMissingError(RuntimeError):
    """Raised when a requested input document cannot be located."""


class RunLogsFileMissingError(RuntimeError):
    """Raised when a run log file is missing/unavailable."""


class RunOutputMissingError(RuntimeError):
    """Raised when a run's output file cannot be located."""


class RunOutputNotReadyError(RuntimeError):
    """Raised when a run output is not yet ready to be downloaded."""


class RunOutputPreviewUnsupportedError(RuntimeError):
    """Raised when a run output preview is requested for an unsupported file type."""


class RunOutputPreviewSheetNotFoundError(RuntimeError):
    """Raised when a requested worksheet is not present in the run output."""


class RunOutputPreviewParseError(RuntimeError):
    """Raised when a run output preview cannot be generated."""


class RunOutputSheetUnsupportedError(RuntimeError):
    """Raised when run output sheets are requested for an unsupported file type."""


class RunOutputSheetParseError(RuntimeError):
    """Raised when run output sheets cannot be listed."""


class RunInputMissingError(RuntimeError):
    """Raised when a run input file cannot be located."""


class RunQueueFullError(RuntimeError):
    """Raised when the run queue is at capacity."""
