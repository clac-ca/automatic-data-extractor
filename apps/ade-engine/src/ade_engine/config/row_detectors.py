"""Row detector discovery for table detection."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from ade_engine.config.validators import require_keyword_only

RowDetectorFn = Callable[..., Any]


@dataclass(frozen=True)
class RowDetector:
    func: RowDetectorFn
    default_label: str | None
    qualified_name: str


def infer_default_label(detector: Callable[..., object]) -> str | None:
    explicit = (
        getattr(detector, "__row_label__", None)
        or getattr(detector, "row_label", None)
        or getattr(detector, "default_label", None)
    )
    if explicit:
        return str(explicit)

    module = getattr(detector, "__module__", "")
    if module.endswith(".header"):
        return "header"
    if module.endswith(".data"):
        return "data"
    return None


def discover_row_detectors(package: ModuleType) -> tuple[RowDetector, ...]:
    """Load and validate row detectors under ``<package>.row_detectors``."""

    try:
        detectors_pkg = importlib.import_module(f"{package.__name__}.row_detectors")
    except ModuleNotFoundError:
        return ()

    detectors: list[RowDetector] = []
    for entry in sorted(resources.files(detectors_pkg).iterdir(), key=lambda e: e.name):
        entry_path = Path(entry.name)
        if entry_path.name.startswith("_") or entry_path.suffix != ".py":
            continue

        module = importlib.import_module(f"{detectors_pkg.__name__}.{entry_path.stem}")
        for name, attr in inspect.getmembers(module, callable):
            if not name.startswith("detect_"):
                continue
            require_keyword_only(attr, label=f"Row detector '{module.__name__}.{name}'")
            detectors.append(
                RowDetector(
                    func=attr,
                    default_label=infer_default_label(attr),
                    qualified_name=f"{module.__name__}.{name}",
                )
            )

    detectors.sort(key=lambda d: d.qualified_name)
    return tuple(detectors)


__all__ = ["RowDetector", "RowDetectorFn", "discover_row_detectors"]
