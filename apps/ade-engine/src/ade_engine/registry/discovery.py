"""Config package discovery utilities."""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable


def import_all(package: str | ModuleType) -> list[str]:
    """Import all submodules under ``package`` to trigger decorator registration.

    Returns a list of fully-qualified module names that were imported. Order is
    deterministic (sorted by module name).
    """

    pkg = package if isinstance(package, ModuleType) else importlib.import_module(package)
    imported: list[str] = []

    if not hasattr(pkg, "__path__"):
        return imported

    modules = sorted(pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."), key=lambda m: m.name)
    for mod in modules:
        importlib.import_module(mod.name)
        imported.append(mod.name)

    return imported


__all__ = ["import_all"]
