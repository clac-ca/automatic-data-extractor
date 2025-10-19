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


class ConfigurationColumnNotFoundError(Exception):
    """Raised when a configuration column cannot be located."""

    def __init__(self, configuration_id: str, canonical_key: str) -> None:
        message = (
            f"Column {canonical_key!r} not found for configuration {configuration_id!r}"
        )
        super().__init__(message)
        self.configuration_id = configuration_id
        self.canonical_key = canonical_key


class ConfigurationColumnValidationError(Exception):
    """Raised when a bulk column update fails validation."""

    def __init__(
        self,
        errors: dict[str, list[str]] | None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(message or "Invalid configuration column payload")
        self.errors = errors or {}

    def __str__(self) -> str:
        base = super().__str__()
        if not self.errors:
            return base
        parts: list[str] = []
        for field, messages in self.errors.items():
            for detail in messages:
                parts.append(f"{field}: {detail}")
        if not parts:
            return base
        return f"{base}: {'; '.join(parts)}"


class ConfigurationScriptVersionNotFoundError(Exception):
    """Raised when a configuration script version lookup fails."""

    def __init__(self, script_version_id: str) -> None:
        super().__init__(f"Configuration script version {script_version_id!r} not found")
        self.script_version_id = script_version_id


class ConfigurationScriptValidationError(Exception):
    """Raised when a configuration script fails validation checks."""

    def __init__(
        self,
        errors: dict[str, list[str]] | None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(message or "Configuration script did not pass validation")
        self.errors = errors or {}

    def __str__(self) -> str:
        base = super().__str__()
        if not self.errors:
            return base
        parts: list[str] = []
        for field, messages in self.errors.items():
            for detail in messages:
                parts.append(f"{field}: {detail}")
        if not parts:
            return base
        return f"{base}: {'; '.join(parts)}"


class ConfigurationScriptVersionOwnershipError(Exception):
    """Raised when a script version does not belong to the target configuration."""

    def __init__(self, script_version_id: str, configuration_id: str) -> None:
        message = (
            f"Script version {script_version_id!r} does not belong to configuration "
            f"{configuration_id!r}"
        )
        super().__init__(message)
        self.script_version_id = script_version_id
        self.configuration_id = configuration_id


__all__ = [
    "ActiveConfigurationNotFoundError",
    "ConfigurationNotFoundError",
    "ConfigurationVersionNotFoundError",
    "ConfigurationVersionMismatchError",
    "ConfigurationColumnNotFoundError",
    "ConfigurationColumnValidationError",
    "ConfigurationScriptValidationError",
    "ConfigurationScriptVersionNotFoundError",
    "ConfigurationScriptVersionOwnershipError",
]
