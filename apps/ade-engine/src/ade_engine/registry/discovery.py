"""Config package discovery utilities."""
from __future__ import annotations

import importlib
import sys
import pkgutil
from types import ModuleType
from typing import Iterable


def _purge_package_modules(package_name: str) -> None:
    """Remove cached modules for a package so decorators re-run on import."""

    to_delete = [
        name
        for name in list(sys.modules.keys())
        if name == package_name or name.startswith(f"{package_name}.")
    ]
    for name in to_delete:
        sys.modules.pop(name, None)
    importlib.invalidate_caches()


def import_all(package: str | ModuleType, *, fresh: bool = False) -> list[str]:
    """Import all submodules under ``package`` to trigger decorator registration.

    When ``fresh`` is True, cached modules for the package are cleared first so
    that decorators run for a new Registry instance (important when processing
    multiple inputs in a single process).

    Returns a list of fully-qualified module names that were imported. Order is
    deterministic (sorted by module name).
    """

    package_name = package.__name__ if isinstance(package, ModuleType) else str(package)
    if fresh:
        _purge_package_modules(package_name)

    pkg = (
        package
        if isinstance(package, ModuleType) and not fresh
        else importlib.import_module(package_name)
    )
    imported: list[str] = []

    if not hasattr(pkg, "__path__"):
        return imported

    modules = sorted(pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."), key=lambda m: m.name)
    for mod in modules:
        importlib.import_module(mod.name)
        imported.append(mod.name)

    return imported


__all__ = ["import_all"]
