"""Domain-specific exceptions for configuration versioning."""

from __future__ import annotations

from typing import Mapping


class ConfigNotFoundError(RuntimeError):
    """Raised when a configuration package cannot be located."""

    def __init__(self, config_id: str) -> None:
        super().__init__(f"Config {config_id!r} not found")
        self.config_id = config_id


class ConfigSlugConflictError(RuntimeError):
    """Raised when creating a config with a duplicate slug."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Config slug {slug!r} already exists")
        self.slug = slug


class ConfigVersionNotFoundError(RuntimeError):
    """Raised when a configuration version cannot be located."""

    def __init__(self, config_version_id: str) -> None:
        super().__init__(f"Config version {config_version_id!r} not found")
        self.config_version_id = config_version_id


class VersionFileNotFoundError(RuntimeError):
    """Raised when a version file cannot be located."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Version file {path!r} not found")
        self.path = path


class VersionFileConflictError(RuntimeError):
    """Raised when optimistic concurrency checks fail for version files."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Version file {path!r} update conflict")
        self.path = path


class ConfigVersionActivationError(RuntimeError):
    """Raised when activating a version is not possible."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigDependentJobsError(RuntimeError):
    """Raised when attempting hard delete on a config that has job dependencies."""

    def __init__(self, config_id: str, counts_by_version: Mapping[str, int]) -> None:
        super().__init__(f"Config {config_id!r} has dependent jobs")
        self.config_id = config_id
        self.counts_by_version = dict(counts_by_version)


class ConfigVersionDependentJobsError(RuntimeError):
    """Raised when attempting hard delete on a version that has job dependencies."""

    def __init__(self, config_version_id: str, job_count: int) -> None:
        super().__init__(f"Config version {config_version_id!r} has dependent jobs")
        self.config_version_id = config_version_id
        self.job_count = job_count


class ConfigInvariantViolationError(RuntimeError):
    """Raised when state transitions would violate invariants."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ManifestValidationError(RuntimeError):
    """Raised when manifest updates violate validation rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


__all__ = [
    "ConfigNotFoundError",
    "ConfigSlugConflictError",
    "ConfigVersionNotFoundError",
    "ConfigDependentJobsError",
    "ConfigInvariantViolationError",
    "ConfigVersionActivationError",
    "ConfigVersionDependentJobsError",
    "ManifestValidationError",
    "VersionFileConflictError",
    "VersionFileNotFoundError",
]
