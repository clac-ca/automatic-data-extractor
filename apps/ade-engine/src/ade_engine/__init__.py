"""Public API for :mod:`ade_engine`."""

from importlib.metadata import PackageNotFoundError, version

from ade_engine.engine import Engine, ExecutedRun, run_inputs
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunResult, RunStatus

try:
    __version__ = version("ade-engine")
except PackageNotFoundError:  # pragma: no cover - source checkout / editable installs
    __version__ = "0.0.0"

__all__ = [
    "Engine",
    "ExecutedRun",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "Settings",
    "run_inputs",
    "__version__",
]
