"""Custom exceptions for configuration build lifecycle management."""

from __future__ import annotations

__all__ = [
    "BuildAlreadyInProgressError",
    "BuildExecutionError",
    "BuildNotFoundError",
    "BuildWorkspaceMismatchError",
]


class BuildNotFoundError(Exception):
    """Raised when the requested build pointer does not exist."""


class BuildAlreadyInProgressError(Exception):
    """Raised when a build is already running and cannot be coalesced."""


class BuildWorkspaceMismatchError(Exception):
    """Raised when a build record does not belong to the expected workspace."""


class BuildExecutionError(Exception):
    """Raised when the builder fails to produce a working virtual environment."""

    def __init__(self, message: str, *, build_id: str) -> None:
        super().__init__(message)
        self.build_id = build_id
