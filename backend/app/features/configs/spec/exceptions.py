"""Custom manifest loading and validation errors for config packages."""

class ManifestError(RuntimeError):
    """Base type for manifest failures."""


class UnsupportedManifestSchemaError(ManifestError):
    """Raised when a manifest declares an unknown schema version."""

    def __init__(self, schema: str | None) -> None:
        super().__init__(f"Unsupported manifest schema: {schema!r}")
        self.schema = schema


class ManifestConversionError(ManifestError):
    """Raised when a legacy manifest cannot be converted."""


class ManifestValidationError(ManifestError):
    """Raised when manifest data fails structural validation."""


class UnsupportedConfigScriptApiVersionError(ManifestError):
    """Raised when a manifest declares an unsupported config script API version."""

    def __init__(self, version: str | None) -> None:
        super().__init__(f"Unsupported config script API version: {version!r}")
        self.version = version


__all__ = [
    "ManifestConversionError",
    "ManifestError",
    "ManifestValidationError",
    "UnsupportedConfigScriptApiVersionError",
    "UnsupportedManifestSchemaError",
]
