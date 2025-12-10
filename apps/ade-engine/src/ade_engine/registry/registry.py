"""Registry container for config callables."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from ade_engine.registry.models import FieldDef, HookName, ScorePatch


@dataclass
class RegisteredFn:
    fn: Callable[..., Any]
    priority: int
    module: str
    qualname: str
    field: str | None = None
    row_kind: str | None = None
    hook_name: HookName | None = None


class Registry:
    """Holds registered fields, detectors, transforms, validators, and hooks."""

    def __init__(self) -> None:
        self.fields: Dict[str, FieldDef] = {}
        self.row_detectors: List[RegisteredFn] = []
        self.column_detectors: List[RegisteredFn] = []
        self.column_transforms: List[RegisteredFn] = []
        self.column_validators: List[RegisteredFn] = []
        self.hooks: Dict[HookName, List[RegisteredFn]] = {name: [] for name in HookName}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sort_key(self, item: RegisteredFn):
        return (-item.priority, item.module, item.qualname)

    def finalize(self) -> None:
        self.row_detectors.sort(key=self._sort_key)
        self.column_detectors.sort(key=self._sort_key)
        self.column_transforms.sort(key=self._sort_key)
        self.column_validators.sort(key=self._sort_key)
        for hook_list in self.hooks.values():
            hook_list.sort(key=self._sort_key)

    # ------------------------------------------------------------------
    # Field registration
    # ------------------------------------------------------------------
    def register_field(self, field_def: FieldDef) -> FieldDef:
        if field_def.name in self.fields:
            raise ValueError(f"Field '{field_def.name}' already registered")
        self.fields[field_def.name] = field_def
        return field_def

    def ensure_field(self, name: str) -> FieldDef:
        existing = self.fields.get(name)
        if existing:
            return existing
        new_def = FieldDef(name=name)
        self.fields[name] = new_def
        return new_def

    # ------------------------------------------------------------------
    # Score normalization
    # ------------------------------------------------------------------
    def normalize_patch(self, current: str, patch: ScorePatch, *, allow_unknown: bool = False) -> dict[str, float]:
        if patch is None:
            return {}
        result: dict[str, float] = {}
        if isinstance(patch, (int, float)):
            if math.isfinite(float(patch)):
                return {current: float(patch)}
            return {}
        if isinstance(patch, dict):
            for key, value in patch.items():
                try:
                    val = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(val):
                    continue
                if not allow_unknown and key not in self.fields:
                    continue
                result[key] = val
        return result

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_row_detector(self, fn: Callable[..., Any], *, row_kind: str, priority: int) -> None:
        self.row_detectors.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                row_kind=row_kind,
            )
        )

    def register_column_detector(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self.ensure_field(field)
        self.column_detectors.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_column_transform(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self.ensure_field(field)
        self.column_transforms.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_column_validator(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self.ensure_field(field)
        self.column_validators.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_hook(self, fn: Callable[..., Any], *, hook_name: HookName, priority: int) -> None:
        self.hooks[hook_name].append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                hook_name=hook_name,
            )
        )


__all__ = ["Registry", "RegisteredFn"]
