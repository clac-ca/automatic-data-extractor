"""Shared helpers for plugin/hook resolution."""

from __future__ import annotations


def _script_to_module(script: str, *, package: str) -> str:
    """Normalize a script path into an importable module name."""

    module = script[:-3] if script.endswith(".py") else script
    module = module.replace("/", ".").replace("-", "_")
    if not module.startswith(package):
        return f"{package}.{module}"
    return module


__all__ = ["_script_to_module"]
