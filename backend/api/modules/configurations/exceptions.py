"""Module-specific exceptions for configurations."""

from __future__ import annotations


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration lookup does not yield a result."""

    def __init__(self, configuration_id: str) -> None:
        super().__init__(f"Configuration {configuration_id!r} not found")
        self.configuration_id = configuration_id


class ActiveConfigurationNotFoundError(Exception):
    """Raised when a document type lacks an active configuration."""

    def __init__(self, document_type: str) -> None:
        super().__init__(f"No active configuration found for {document_type!r}")
        self.document_type = document_type


class ConfigurationMismatchError(Exception):
    """Raised when a configuration does not match the expected document type."""

    def __init__(
        self,
        configuration_id: str,
        *,
        expected_document_type: str,
        actual_document_type: str,
    ) -> None:
        message = (
            "Configuration "
            f"{configuration_id!r} belongs to document type "
            f"{actual_document_type!r}, not {expected_document_type!r}"
        )
        super().__init__(message)
        self.configuration_id = configuration_id
        self.expected_document_type = expected_document_type
        self.actual_document_type = actual_document_type


class ConfigurationVersionNotFoundError(Exception):
    """Raised when a document type lacks the requested configuration version."""

    def __init__(self, document_type: str, version: int) -> None:
        message = (
            f"Configuration version {version} not found for {document_type!r}"
        )
        super().__init__(message)
        self.document_type = document_type
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
    "ConfigurationMismatchError",
    "ConfigurationNotFoundError",
    "ConfigurationVersionNotFoundError",
    "ConfigurationVersionMismatchError",
]
