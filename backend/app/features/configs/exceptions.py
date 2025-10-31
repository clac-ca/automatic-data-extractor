"""Exception types for the configuration engine."""

from __future__ import annotations


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


__all__ = [
    "ConfigActivationError",
    "ConfigError",
    "ConfigExportError",
    "ConfigFileNotFoundError",
    "ConfigFileOperationError",
    "ConfigImportError",
    "ConfigNotFoundError",
    "ConfigSecretNotFoundError",
    "ConfigStatusConflictError",
    "ManifestInvalidError",
]
