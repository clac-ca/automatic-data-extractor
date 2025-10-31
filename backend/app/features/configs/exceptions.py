"""Domain-specific errors for config operations."""

"""Domain-specific exceptions raised by the configs feature."""


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

    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = [
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigSlugConflictError",
    "ConfigVersionNotFoundError",
    "InvalidConfigManifestError",
]
