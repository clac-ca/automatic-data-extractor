"""Contextvar-backed active registry helper."""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

from ade_engine.registry.registry import Registry

_registry_var: contextvars.ContextVar[Registry | None] = contextvars.ContextVar(
    "ade_engine.registry.current", default=None
)


class RegistryNotActiveError(RuntimeError):
    pass


def set_current_registry(registry: Registry):
    return _registry_var.set(registry)


def reset_current_registry(token) -> None:
    _registry_var.reset(token)


def get_current_registry() -> Registry:
    reg = _registry_var.get()
    if reg is None:
        raise RegistryNotActiveError("No active Registry; call set_current_registry first")
    return reg


@contextmanager
def registry_context(registry: Registry) -> Iterator[Registry]:
    token = set_current_registry(registry)
    try:
        yield registry
    finally:
        reset_current_registry(token)


__all__ = [
    "get_current_registry",
    "registry_context",
    "reset_current_registry",
    "set_current_registry",
    "RegistryNotActiveError",
]
