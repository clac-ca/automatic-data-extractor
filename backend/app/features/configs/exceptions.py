"""Domain-specific exceptions for configuration versioning."""

from __future__ import annotations


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


class DraftVersionNotFoundError(RuntimeError):
    """Raised when a draft version is required but missing."""

    def __init__(self, config_id: str) -> None:
        super().__init__(f"Draft version not found for config {config_id!r}")
        self.config_id = config_id


class DraftFileNotFoundError(RuntimeError):
    """Raised when a draft file cannot be located."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Draft file {path!r} not found")
        self.path = path


class DraftFileConflictError(RuntimeError):
    """Raised when optimistic concurrency checks fail for draft files."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Draft file {path!r} update conflict")
        self.path = path


class ConfigPublishConflictError(RuntimeError):
    """Raised when attempting to publish without a valid draft or semver."""

    pass


class ConfigRevertUnavailableError(RuntimeError):
    """Raised when no candidate version is available to revert to."""

    def __init__(self, config_id: str) -> None:
        super().__init__(f"No published history to revert for config {config_id!r}")
        self.config_id = config_id


class ManifestValidationError(RuntimeError):
    """Raised when manifest updates violate validation rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


__all__ = [
    "ConfigNotFoundError",
    "ConfigSlugConflictError",
    "ConfigVersionNotFoundError",
    "ConfigPublishConflictError",
    "ConfigRevertUnavailableError",
    "DraftFileConflictError",
    "DraftFileNotFoundError",
    "DraftVersionNotFoundError",
    "ManifestValidationError",
]

