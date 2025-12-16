"""Config package loading.

A config package is a Python package on disk (usually ``ade_config``) that exposes:

    def register(registry): ...

The engine loads it by temporarily adding an import root to ``sys.path`` and importing
the package by name. To avoid cross-run contamination when package names repeat
(common with ``ade_config``), we purge any existing modules under that package name
before importing.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfigImport:
    """How to import a config package."""

    package_name: str
    import_root: Path


def resolve_config_import(config_dir: Path) -> ConfigImport:
    """Resolve a filesystem directory into (package_name, import_root).

    Supported layouts:
    - Package directory itself: ``<dir>/<package>/__init__.py``
    - Flat root with ``ade_config``: ``<dir>/ade_config/__init__.py``
    - Src layout: ``<dir>/src/<package>/__init__.py`` (prefers ``ade_config``)
    """

    path = Path(config_dir).expanduser().resolve()
    if not path.exists():
        raise ModuleNotFoundError(f"Config package path does not exist: {path}")
    if path.is_file():
        raise ModuleNotFoundError(f"Config package path must be a directory: {path}")

    # Case 1: path points directly at a package directory.
    if (path / "__init__.py").is_file() and path.name.isidentifier():
        return ConfigImport(package_name=path.name, import_root=path.parent)

    # Case 2: src layout (prefer ade_config if present).
    src_dir = path / "src"
    if src_dir.is_dir():
        packages = [
            p
            for p in src_dir.iterdir()
            if p.is_dir() and p.name.isidentifier() and (p / "__init__.py").is_file()
        ]
        packages.sort(key=lambda p: (p.name != "ade_config", p.name))
        if packages:
            chosen = packages[0]
            return ConfigImport(package_name=chosen.name, import_root=src_dir)

    # Case 3: flat layout with ade_config under the root.
    ade_pkg = path / "ade_config"
    if ade_pkg.is_dir() and (ade_pkg / "__init__.py").is_file():
        return ConfigImport(package_name="ade_config", import_root=path)

    raise ModuleNotFoundError(f"Could not locate a Python package under {path}")


@contextmanager
def _sys_path_root(path: Path):
    root = str(Path(path).expanduser().resolve())
    original = list(sys.path)
    try:
        if root not in sys.path:
            sys.path.insert(0, root)
        yield
    finally:
        sys.path[:] = original


def _purge_modules(package_name: str) -> None:
    # Remove the package module and anything under it (e.g., ade_config.*).
    prefix = f"{package_name}."
    for name in list(sys.modules.keys()):
        if name == package_name or name.startswith(prefix):
            sys.modules.pop(name, None)


def import_and_register(config_dir: Path, *, registry) -> str:
    """Import config package under ``config_dir`` and call ``register(registry)``.

    Returns the resolved entrypoint string (e.g., ``ade_config.register``).
    """

    spec = resolve_config_import(config_dir)
    with _sys_path_root(spec.import_root):
        importlib.invalidate_caches()
        _purge_modules(spec.package_name)
        module = importlib.import_module(spec.package_name)

        register_fn = getattr(module, "register", None)
        if not callable(register_fn):
            raise ModuleNotFoundError(
                f"Config package '{spec.package_name}' must define a register(registry) entrypoint"
            )

        register_fn(registry)
        return f"{spec.package_name}.register"


__all__ = ["ConfigImport", "import_and_register", "resolve_config_import"]
