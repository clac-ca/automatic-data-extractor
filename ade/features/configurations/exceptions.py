"""Module-specific exceptions for configurations."""

from __future__ import annotations


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration lookup does not yield a result."""

    def __init__(self, configuration_id: str) -> None:
        super().__init__(f"Configuration {configuration_id!r} not found")
        self.configuration_id = configuration_id


class ActiveConfigurationNotFoundError(Exception):
    """Raised when a workspace lacks an active configuration."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(f"No active configuration found for workspace {workspace_id!r}")
        self.workspace_id = workspace_id


class ConfigurationVersionNotFoundError(Exception):
    """Raised when a workspace lacks the requested configuration version."""

    def __init__(self, workspace_id: str, version: int) -> None:
        message = f"Configuration version {version} not found for workspace {workspace_id!r}"
        super().__init__(message)
        self.workspace_id = workspace_id
        self.version = version


class ConfigurationVersionMismatchError(Exception):
    """Raised when a configuration revision does not match the expected version."""

    def __init__(
        self,
        configuration_id: str,
        *,
        expected_version: int,
        actual_version: int,
    ) -> None:
        message = (
            f"Configuration {configuration_id!r} is version {actual_version}, "
            f"not {expected_version}"
        )
        super().__init__(message)
        self.configuration_id = configuration_id
        self.expected_version = expected_version
        self.actual_version = actual_version


__all__ = [
    "ActiveConfigurationNotFoundError",
    "ConfigurationNotFoundError",
    "ConfigurationVersionNotFoundError",
    "ConfigurationVersionMismatchError",
]
