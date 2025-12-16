"""Public API for :mod:`ade_engine`."""

from importlib import metadata

from ade_engine.application.engine import Engine
from ade_engine.models import (
    FieldDef,
    HookName,
    RowKind,
)
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.run import RunRequest, RunResult, RunStatus

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
