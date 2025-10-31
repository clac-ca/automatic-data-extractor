"""Domain exceptions used by the configuration engine."""

from __future__ import annotations

from collections.abc import Mapping


class ConfigError(RuntimeError):
    """Base error for configuration engine failures."""


class ConfigNotFoundError(ConfigError):
    """Raised when a configuration bundle cannot be located for a workspace."""

    def __init__(self, workspace_id: str, config_id: str) -> None:
        super().__init__(f"Config {config_id!r} not found in workspace {workspace_id!r}")
        self.workspace_id = workspace_id
        self.config_id = config_id


class ConfigStatusConflictError(ConfigError):
    """Raised when attempting an operation that violates status invariants."""

    def __init__(self, config_id: str, status: str, message: str | None = None) -> None:
        detail = message or f"Config {config_id!r} is in status {status!r}"
        super().__init__(detail)
        self.config_id = config_id
        self.status = status


class ConfigFileNotFoundError(ConfigError):
    """Raised when attempting to access a file that is not part of the bundle."""

    def __init__(self, config_id: str, path: str) -> None:
        super().__init__(f"Config {config_id!r} does not contain file {path!r}")
        self.config_id = config_id
        self.path = path


class ConfigFileOperationError(ConfigError):
    """Raised when file mutations fail due to validation or I/O issues."""

    def __init__(self, config_id: str, path: str, message: str) -> None:
        super().__init__(message)
        self.config_id = config_id
        self.path = path


class ConfigActivationError(ConfigError):
    """Raised when activating a configuration bundle fails."""

    def __init__(self, config_id: str, message: str) -> None:
        super().__init__(message)
        self.config_id = config_id


class ManifestInvalidError(ConfigError):
    """Raised when a manifest payload fails validation."""

    def __init__(self, config_id: str, message: str) -> None:
        super().__init__(message)
        self.config_id = config_id


class PlaintextSecretRejectedError(ConfigError):
    """Raised when callers attempt to persist plaintext secrets into the manifest."""

    def __init__(self, config_id: str, key: str) -> None:
        super().__init__(f"Plaintext secret provided for {key!r} in config {config_id!r}")
        self.config_id = config_id
        self.key = key


class ConfigSecretNotFoundError(ConfigError):
    """Raised when attempting to access a manifest secret that does not exist."""

    def __init__(self, config_id: str, key: str) -> None:
        super().__init__(f"Secret {key!r} not found in config {config_id!r}")
        self.config_id = config_id
        self.key = key


class ConfigImportError(ConfigError):
    """Raised when importing a configuration archive fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConfigExportError(ConfigError):
    """Raised when exporting a configuration archive fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConfigSlugConflictError(ConfigError):
    """Raised when creating a configuration with a duplicate slug."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Config slug {slug!r} already exists")
        self.slug = slug


class ConfigVersionNotFoundError(ConfigError):
    """Raised when a referenced configuration version cannot be located."""

    def __init__(self, config_version_id: str) -> None:
        super().__init__(f"Config version {config_version_id!r} not found")
        self.config_version_id = config_version_id


class VersionFileNotFoundError(ConfigError):
    """Raised when an expected configuration version file is missing."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Version file {path!r} not found")
        self.path = path


class VersionFileConflictError(ConfigError):
    """Raised when optimistic concurrency checks fail for version files."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Version file {path!r} update conflict")
        self.path = path


class ConfigVersionActivationError(ConfigError):
    """Raised when activating a legacy configuration version is not possible."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigDependentJobsError(ConfigError):
    """Raised when deleting a legacy configuration that still has job dependencies."""

    def __init__(self, config_id: str, counts_by_version: Mapping[str, int]) -> None:
        super().__init__(f"Config {config_id!r} has dependent jobs")
        self.config_id = config_id
        self.counts_by_version = dict(counts_by_version)


class ConfigVersionDependentJobsError(ConfigError):
    """Raised when deleting a legacy configuration version with job dependencies."""

    def __init__(self, config_version_id: str, job_count: int) -> None:
        super().__init__(f"Config version {config_version_id!r} has dependent jobs")
        self.config_version_id = config_version_id
        self.job_count = job_count


class ConfigInvariantViolationError(ConfigError):
    """Raised when state transitions would violate legacy configuration invariants."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ManifestValidationError(ConfigError):
    """Raised when manifest updates violate validation rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


__all__ = [
    "ConfigActivationError",
    "ConfigDependentJobsError",
    "ConfigError",
    "ConfigExportError",
    "ConfigFileNotFoundError",
    "ConfigFileOperationError",
    "ConfigImportError",
    "ConfigInvariantViolationError",
    "ConfigNotFoundError",
    "ConfigSlugConflictError",
    "ConfigStatusConflictError",
    "ConfigSecretNotFoundError",
    "ConfigVersionActivationError",
    "ConfigVersionDependentJobsError",
    "ConfigVersionNotFoundError",
    "ManifestInvalidError",
    "ManifestValidationError",
    "PlaintextSecretRejectedError",
    "VersionFileConflictError",
    "VersionFileNotFoundError",
]
