"""Utilities for importing config package modules at runtime."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(slots=True)
class LoadedColumnModule:
    field_name: str
    path: str
    module: ModuleType


@dataclass(slots=True)
class LoadedHookModule:
    name: str
    path: str
    module: ModuleType


@dataclass(slots=True)
class LoadedRowModule:
    path: str
    module: ModuleType


HOOK_GROUPS: tuple[str, ...] = (
    "on_activate",
    "on_job_start",
    "on_after_extract",
    "after_mapping",
    "after_transform",
    "after_validate",
    "on_job_end",
)


class ConfigPackageLoader:
    """Import column, hook, and row detector modules from a stored config package."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def load_column_modules(self, manifest: dict[str, Any]) -> list[LoadedColumnModule]:
        columns = manifest.get("columns") or {}
        order = list(columns.get("order") or [])
        meta = columns.get("meta") or {}
        loaded: list[LoadedColumnModule] = []
        for field in order:
            details = meta.get(field) or {}
            script = details.get("script")
            enabled = details.get("enabled", True)
            if not script or not enabled:
                continue
            module = self._load_module(script)
            loaded.append(
                LoadedColumnModule(
                    field_name=field,
                    path=script,
                    module=module,
                )
            )
        return loaded

    def load_hook_modules(self, manifest: dict[str, Any]) -> dict[str, list[LoadedHookModule]]:
        hooks_section = manifest.get("hooks") or {}
        loaded: dict[str, list[LoadedHookModule]] = {}
        for hook_name in HOOK_GROUPS:
            entries = hooks_section.get(hook_name)
            if not isinstance(entries, list):
                loaded[hook_name] = []
                continue
            bucket: list[LoadedHookModule] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("enabled", True):
                    continue
                script = entry.get("script")
                if not script:
                    continue
                module = self._load_module(script)
                bucket.append(
                    LoadedHookModule(
                        name=hook_name,
                        path=script,
                        module=module,
                    )
                )
            loaded[hook_name] = bucket
        return loaded

    def load_row_type_modules(self) -> list[LoadedRowModule]:
        """Load every module under ``row_types/`` for Pass 1 detectors."""

        target_dir = (self._root / "row_types").resolve()
        if not target_dir.exists():
            return []
        loaded: list[LoadedRowModule] = []
        for module_path in sorted(target_dir.glob("*.py")):
            if module_path.name == "__init__.py":
                continue
            relative = module_path.relative_to(self._root).as_posix()
            module = self._load_module(relative)
            loaded.append(LoadedRowModule(path=relative, module=module))
        return loaded

    def _load_module(self, relative_path: str) -> ModuleType:
        target = (self._root / relative_path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"Module {relative_path} does not exist inside config package")

        if self._root not in target.parents and target != self._root:
            raise ValueError(f"Module path {relative_path} escapes the config package")

        module_name = f"ade_config.{relative_path.replace('/', '.').rsplit('.py', 1)[0]}"
        spec = importlib.util.spec_from_file_location(module_name, target)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module at {relative_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        return module


__all__ = [
    "ConfigPackageLoader",
    "LoadedColumnModule",
    "LoadedHookModule",
    "LoadedRowModule",
]
