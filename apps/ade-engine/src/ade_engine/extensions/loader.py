"""Config package loading.

A config package is a Python package on disk (often ``ade_config``) containing plugin
modules under:

- ``<package>/columns/``
- ``<package>/row_detectors/``
- ``<package>/hooks/``

Any module in those folders that defines a top-level ``register(registry)`` function
will be imported and invoked by the engine (deterministic order; no central list).

The engine loads a config package by temporarily adding an import root to ``sys.path``
and importing modules by dotted name. To avoid cross-run contamination when package
names repeat (common with ``ade_config``), we purge any existing modules under that
package name before importing.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfigImport:
    """How to import a config package."""

    package_name: str
    import_root: Path


_PLUGIN_SUBPACKAGES: tuple[str, ...] = ("columns", "row_detectors", "hooks")


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


def _should_skip_path_parts(*, parts: tuple[str, ...]) -> bool:
    return any(part == "tests" or (part.startswith("_") and part != "__init__.py") for part in parts)


def _has_top_level_register(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ModuleNotFoundError(f"Config module has invalid Python syntax: {path} ({exc})") from exc

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "register":
            return True
    return False


def _iter_registerable_modules(*, spec: ConfigImport) -> list[str]:
    package_dir = (Path(spec.import_root) / spec.package_name).resolve()
    modules: list[str] = []

    for subpkg in _PLUGIN_SUBPACKAGES:
        root = package_dir / subpkg
        if not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip-directories for speed and determinism.
            dirnames[:] = sorted(
                d for d in dirnames if d != "__pycache__" and not _should_skip_path_parts(parts=(d,))
            )

            rel_dir = Path(dirpath).resolve().relative_to(package_dir)
            if _should_skip_path_parts(parts=rel_dir.parts):
                continue

            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("_") and filename != "__init__.py":
                    continue

                path = Path(dirpath) / filename
                rel = path.resolve().relative_to(package_dir)
                if _should_skip_path_parts(parts=rel.parts):
                    continue

                if not _has_top_level_register(path):
                    continue

                parts = [spec.package_name, *rel.parts]
                parts[-1] = parts[-1][:-3]  # drop ".py"
                if parts[-1] == "__init__":
                    parts.pop()
                modules.append(".".join(parts))

    # Deterministic import/call order.
    return sorted(set(modules))


def import_and_register(config_dir: Path, *, registry) -> list[str]:
    """Import config package under ``config_dir`` and register plugin modules.

    Returns the list of module names whose ``register(registry)`` was invoked.
    """

    spec = resolve_config_import(config_dir)
    with _sys_path_root(spec.import_root):
        importlib.invalidate_caches()
        _purge_modules(spec.package_name)
        importlib.import_module(spec.package_name)  # Ensure the package itself imports.

        module_names = _iter_registerable_modules(spec=spec)
        if not module_names:
            expected = ", ".join(f"{spec.package_name}.{p}" for p in _PLUGIN_SUBPACKAGES)
            raise ModuleNotFoundError(
                f"Config package '{spec.package_name}' contains no plugin modules with register(registry) under: {expected}"
            )

        for module_name in module_names:
            module = importlib.import_module(module_name)
            register_fn = getattr(module, "register", None)
            if not callable(register_fn):
                raise ModuleNotFoundError(
                    f"Plugin module '{module_name}' must define a callable register(registry)"
                )
            register_fn(registry)

        return module_names


__all__ = ["ConfigImport", "import_and_register", "resolve_config_import"]
