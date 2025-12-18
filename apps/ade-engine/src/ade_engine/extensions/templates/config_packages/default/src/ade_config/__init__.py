"""Example ADE config package.

Drop modules into:
- ``ade_config/columns`` (fields + column detectors/transforms/validators)
- ``ade_config/row_detectors`` (row kind detectors)
- ``ade_config/hooks`` (lifecycle hooks)

Each module should expose ``register(registry)``. This top-level entrypoint will
discover and call them automatically (deterministic order; no central list).
"""

from __future__ import annotations

from importlib import import_module
from pkgutil import walk_packages
from types import ModuleType


def _should_skip(module_name: str) -> bool:
    parts = module_name.split(".")
    return any(part.startswith("_") or part == "tests" for part in parts)


def _iter_register_modules(package: ModuleType) -> list[str]:
    package_paths = getattr(package, "__path__", None)
    if not package_paths:
        return []

    names: set[str] = set()
    for mod in walk_packages(package_paths, prefix=f"{package.__name__}."):
        if mod.ispkg:
            continue
        if _should_skip(mod.name):
            continue
        names.add(mod.name)

    return sorted(names)


def _register_all(registry, package_name: str) -> None:
    try:
        package = import_module(package_name)
    except ModuleNotFoundError:
        return

    for module_name in _iter_register_modules(package):
        module = import_module(module_name)
        register_fn = getattr(module, "register", None)
        if callable(register_fn):
            register_fn(registry)


def register(registry) -> None:
    """Register all config modules (columns, row detectors, hooks)."""
    _register_all(registry, "ade_config.columns")
    _register_all(registry, "ade_config.row_detectors")
    _register_all(registry, "ade_config.hooks")
