"""Shared validation helpers for config-driven callables."""

from __future__ import annotations

import inspect
from typing import Callable

from ade_engine.exceptions import ConfigError


def require_keyword_only(func: Callable[..., object], *, label: str) -> None:
    """Ensure a config-provided callable uses keyword-only parameters.

    We enforce this so the engine can evolve the kwargs surface area without
    breaking older scripts (callables must also accept ``**_``).
    """

    signature = inspect.signature(func)
    positional = [
        p
        for p in signature.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if positional:
        names = ", ".join(p.name for p in positional)
        raise ConfigError(f"{label} must declare keyword-only parameters (invalid: {names})")

    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
        raise ConfigError(f"{label} must accept **_ for forwards compatibility")


__all__ = ["require_keyword_only"]
