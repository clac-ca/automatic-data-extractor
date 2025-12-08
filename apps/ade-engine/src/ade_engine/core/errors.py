"""Backward-compatible import shim for ``ade_engine.core.errors``.

New code should import from :mod:`ade_engine.exceptions`.
"""

from ade_engine.exceptions import AdeEngineError, ConfigError, HookError, InputError, PipelineError

__all__ = ["AdeEngineError", "ConfigError", "InputError", "HookError", "PipelineError"]
