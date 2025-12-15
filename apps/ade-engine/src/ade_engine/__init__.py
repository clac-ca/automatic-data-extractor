"""Public API for :mod:`ade_engine`."""

from importlib import metadata

from ade_engine.engine import Engine
from ade_engine.registry import (
    FieldDef,
    HookName,
    RowKind,
)
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunResult, RunStatus

try:
    __version__ = metadata.version("ade-engine")
except metadata.PackageNotFoundError:  # pragma: no cover - source checkout / editable installs
    __version__ = "0.0.0"

__all__ = [
    "Engine",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "Settings",
    "FieldDef",
    "HookName",
    "RowKind",
    "__version__",
]
