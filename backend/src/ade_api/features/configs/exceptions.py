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


class ConfigImportError(Exception):
    """Raised when archives cannot be imported safely."""

    def __init__(
        self,
        code: str,
        *,
        detail: str | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.limit = limit


class ConfigEngineDependencyMissingError(Exception):
    """Raised when a config package does not declare ade-engine."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__("engine_dependency_missing")
        self.detail = detail


__all__ = [
    "ConfigEngineDependencyMissingError",
    "ConfigImportError",
    "ConfigPublishConflictError",
    "ConfigSourceInvalidError",
    "ConfigSourceNotFoundError",
    "ConfigStateError",
    "ConfigStorageNotFoundError",
    "ConfigValidationFailedError",
    "ConfigurationNotFoundError",
]
