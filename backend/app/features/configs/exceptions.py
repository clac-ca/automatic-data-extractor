"""Domain-specific errors for config operations."""

from typing import Sequence


class ConfigError(RuntimeError):
    """Base error for config operations."""


class ConfigNotFoundError(ConfigError):
    """Raised when a config or its metadata is not present."""

    def __init__(self, config_id: str) -> None:
        super().__init__(f"Config {config_id} was not found")
        self.config_id = config_id


class ConfigSlugConflictError(ConfigError):
    """Raised when attempting to reuse a workspace config slug."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Config slug {slug!r} already exists for this workspace")
        self.slug = slug


class ConfigVersionNotFoundError(ConfigError):
    """Raised when a requested config version cannot be located."""

    def __init__(self, config_version_id: str) -> None:
        super().__init__(f"Config version {config_version_id} was not found")
        self.config_version_id = config_version_id


class InvalidConfigManifestError(ConfigError):
    """Raised when a manifest payload fails validation."""

    def __init__(self, message: str, *, diagnostics: Sequence[object] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])


class ConfigDraftNotFoundError(ConfigError):
    """Raised when a requested draft cannot be located."""

    def __init__(self, draft_id: str) -> None:
        super().__init__(f"Config draft {draft_id} was not found")
        self.draft_id = draft_id


class ConfigDraftConflictError(ConfigError):
    """Raised when a draft write encounters a concurrent modification."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Draft file conflict at {path}")
        self.path = path


class ConfigDraftFileTypeError(ConfigError):
    """Raised when attempting to read or write an unsupported draft file type."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Draft file {path} is not a UTF-8 text file")
        self.path = path


class ConfigActivationError(ConfigError):
    """Raised when a config version cannot be activated."""

    def __init__(self, message: str, *, diagnostics: Sequence[object] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])


__all__ = [
    "ConfigError",
    "ConfigActivationError",
    "ConfigDraftConflictError",
    "ConfigDraftFileTypeError",
    "ConfigDraftNotFoundError",
    "ConfigNotFoundError",
    "ConfigSlugConflictError",
    "ConfigVersionNotFoundError",
    "InvalidConfigManifestError",
]
