"""Hook runtime for lifecycle callbacks defined in the manifest."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

from ade_engine.config.manifest import ManifestContext
from ade_engine.config.validators import require_keyword_only
from ade_engine.exceptions import ConfigError

HookFn = Callable[..., Any]


@dataclass(frozen=True)
class HooksRuntime:
    """Resolved hook callables for each lifecycle stage."""

    on_workbook_start: tuple[HookFn, ...] = ()
    on_sheet_start: tuple[HookFn, ...] = ()
    on_table_detected: tuple[HookFn, ...] = ()
    on_table_mapped: tuple[HookFn, ...] = ()
    on_table_written: tuple[HookFn, ...] = ()
    on_workbook_before_save: tuple[HookFn, ...] = ()

    @classmethod
    def from_manifest(cls, *, package: ModuleType, manifest: ManifestContext) -> "HooksRuntime":
        hooks_pkg_name = f"{package.__name__}.hooks"
        try:
            hooks_pkg = importlib.import_module(hooks_pkg_name)
        except ModuleNotFoundError:
            hooks_pkg = None

        def resolve_ref(ref: str) -> str:
            # Allow absolute module paths in the manifest; otherwise resolve under <pkg>.hooks.
            return ref if "." in ref else f"{hooks_pkg_name}.{ref}"

        def load_entrypoint(module_path: str) -> HookFn:
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as exc:
                raise ConfigError(f"Hook module '{module_path}' could not be imported") from exc

            entrypoint = getattr(module, "run", None) or getattr(module, "main", None)
            if entrypoint is None or not callable(entrypoint):
                raise ConfigError(f"Hook module '{module_path}' must define a callable 'run' or 'main'")

            require_keyword_only(entrypoint, label=f"Hook '{module_path}'")
            return entrypoint

        def load_unique(refs: Iterable[str]) -> tuple[HookFn, ...]:
            seen: set[str] = set()
            out: list[HookFn] = []
            for ref in refs:
                module_path = resolve_ref(ref)
                if module_path in seen:
                    continue
                seen.add(module_path)
                out.append(load_entrypoint(module_path))
            return tuple(out)

        hooks_cfg = manifest.hooks
        explicit = [
            hooks_cfg.on_workbook_start,
            hooks_cfg.on_sheet_start,
            hooks_cfg.on_table_detected,
            hooks_cfg.on_table_mapped,
            hooks_cfg.on_table_written,
            hooks_cfg.on_workbook_before_save,
        ]

        if any(explicit):
            return cls(
                on_workbook_start=load_unique(hooks_cfg.on_workbook_start),
                on_sheet_start=load_unique(hooks_cfg.on_sheet_start),
                on_table_detected=load_unique(hooks_cfg.on_table_detected),
                on_table_mapped=load_unique(hooks_cfg.on_table_mapped),
                on_table_written=load_unique(hooks_cfg.on_table_written),
                on_workbook_before_save=load_unique(hooks_cfg.on_workbook_before_save),
            )

        # Backwards-compatible fallback: load every hooks/*.py for every stage.
        if hooks_pkg is None:
            return cls()

        loaded: list[HookFn] = []
        for hook_file in sorted(resources.files(hooks_pkg).iterdir(), key=lambda p: p.name):
            hook_path = Path(hook_file.name)
            if hook_path.name.startswith("_") or hook_path.suffix != ".py":
                continue
            loaded.append(load_entrypoint(f"{hooks_pkg_name}.{hook_path.stem}"))

        hooks_tuple = tuple(loaded)
        return cls(
            on_workbook_start=hooks_tuple,
            on_sheet_start=hooks_tuple,
            on_table_detected=hooks_tuple,
            on_table_mapped=hooks_tuple,
            on_table_written=hooks_tuple,
            on_workbook_before_save=hooks_tuple,
        )


__all__ = ["HooksRuntime"]
