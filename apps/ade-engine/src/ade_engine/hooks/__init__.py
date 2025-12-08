"""Hook interfaces and helpers."""

from ade_engine.hooks.base import BaseHooks
from ade_engine.hooks.dispatcher import HookDispatcher
from ade_engine.hooks.protocol import ADEHooks

__all__ = ["BaseHooks", "HookDispatcher", "ADEHooks"]
