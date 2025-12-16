"""Engine error hierarchy."""

from __future__ import annotations


class AdeEngineError(Exception):
    """Base class for engine-specific exceptions."""


class ConfigError(AdeEngineError):
    """Raised when manifest or config scripts are invalid."""


class InputError(AdeEngineError):
    """Raised when source files or sheets are unusable."""


class HookError(AdeEngineError):
    """Raised when hooks fail during execution."""

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage


class PipelineError(AdeEngineError):
    """Raised for unexpected pipeline failures."""


__all__ = [
    "AdeEngineError",
    "ConfigError",
    "InputError",
    "HookError",
    "PipelineError",
]
