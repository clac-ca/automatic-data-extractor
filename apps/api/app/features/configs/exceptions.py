"""Domain-specific exceptions for configuration operations."""

from __future__ import annotations

from collections.abc import Sequence

from .schemas import ConfigValidationIssue


class ConfigSourceNotFoundError(Exception):
    """Raised when the requested template or clone source is missing."""


class ConfigPublishConflictError(Exception):
    """Raised when publishing a configuration collides with an existing folder."""


class ConfigSourceInvalidError(Exception):
    """Raised when validation fails for the source tree."""

    def __init__(self, issues: Sequence[ConfigValidationIssue]) -> None:
        super().__init__("invalid_source_shape")
        self.issues = list(issues)


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration record cannot be resolved."""


class ConfigStorageNotFoundError(Exception):
    """Raised when configuration files are missing on disk."""


class ConfigValidationFailedError(Exception):
    """Raised when validation produces issues during lifecycle actions."""

    def __init__(self, issues: Sequence[ConfigValidationIssue]) -> None:
        super().__init__("validation_failed")
        self.issues = list(issues)


class ConfigStateError(Exception):
    """Raised when lifecycle transitions are not permitted."""


__all__ = [
    "ConfigPublishConflictError",
    "ConfigSourceInvalidError",
    "ConfigSourceNotFoundError",
    "ConfigStateError",
    "ConfigStorageNotFoundError",
    "ConfigValidationFailedError",
    "ConfigurationNotFoundError",
]
