"""Engine error hierarchy and helpers."""
from __future__ import annotations

from .types import RunError, RunErrorCode, RunPhase


class AdeEngineError(Exception):
    """Base class for engine-specific exceptions."""


class ConfigError(AdeEngineError):
    """Raised when manifest or config scripts are invalid."""


class InputError(AdeEngineError):
    """Raised when source files or sheets are unusable."""


class HookError(AdeEngineError):
    """Raised when hooks fail during execution."""


class PipelineError(AdeEngineError):
    """Raised for unexpected pipeline failures."""


def error_to_run_error(exc: BaseException, *, stage: RunPhase | None = None) -> RunError:
    """Map any exception to a structured :class:`RunError`.

    Config/Input/Hook/Pipeline errors map to their respective ``RunErrorCode`` values.
    Unknown exceptions fall back to ``UNKNOWN_ERROR`` with the exception message.
    """

    code: RunErrorCode
    if isinstance(exc, ConfigError):
        code = RunErrorCode.CONFIG_ERROR
    elif isinstance(exc, InputError):
        code = RunErrorCode.INPUT_ERROR
    elif isinstance(exc, HookError):
        code = RunErrorCode.HOOK_ERROR
    elif isinstance(exc, PipelineError):
        code = RunErrorCode.PIPELINE_ERROR
    else:
        code = RunErrorCode.UNKNOWN_ERROR

    message = str(exc) or exc.__class__.__name__
    return RunError(code=code, stage=stage, message=message)


__all__ = [
    "AdeEngineError",
    "ConfigError",
    "InputError",
    "HookError",
    "PipelineError",
    "error_to_run_error",
]
