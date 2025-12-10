"""Public API for :mod:`ade_engine`."""

from importlib import metadata

from ade_engine.engine import Engine, ExecutedRun, run_inputs
from ade_engine.registry import (
    FieldDef,
    HookName,
    RowKind,
    column_detector,
    column_transform,
    column_validator,
    field_meta,
    hook,
    row_detector,
)
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunResult, RunStatus

try:
    __version__ = metadata.version("ade-engine")
except metadata.PackageNotFoundError:  # pragma: no cover - source checkout / editable installs
    __version__ = "0.0.0"

__all__ = [
    "Engine",
    "ExecutedRun",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "Settings",
    "run_inputs",
    "FieldDef",
    "HookName",
    "RowKind",
    "row_detector",
    "column_detector",
    "column_transform",
    "column_validator",
    "field_meta",
    "hook",
    "__version__",
]
