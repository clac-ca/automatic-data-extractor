"""Domain exceptions for the runs feature."""

from __future__ import annotations

__all__ = [
    "RunNotFoundError",
    "RunDocumentMissingError",
    "RunLogsFileMissingError",
    "RunOutputMissingError",
    "RunOutputNotReadyError",
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


class RunInputMissingError(RuntimeError):
    """Raised when a run input file cannot be located."""


class RunQueueFullError(RuntimeError):
    """Raised when the run queue is at capacity."""
