"""Public API for :mod:`ade_engine`."""

from pkg_resources import DistributionNotFound, get_distribution  # type: ignore[import-untyped]

from ade_engine.engine import Engine, ExecutedRun, run_inputs
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunResult, RunStatus

try:
    __version__ = get_distribution("ade-engine").version
except DistributionNotFound:  # pragma: no cover - source checkout / editable installs
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
