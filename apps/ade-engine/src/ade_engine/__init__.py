"""Public API for ade_engine."""

from ade_engine.core.engine import Engine
from ade_engine.core.types import EngineInfo, RunRequest, RunResult, RunStatus

__version__ = "1.6.0"


def run(*args, **kwargs) -> RunResult:
    """Convenience helper to execute a single run."""

    engine = Engine()
    return engine.run(*args, **kwargs)


__all__ = [
    "Engine",
    "run",
    "RunRequest",
    "RunResult",
    "EngineInfo",
    "RunStatus",
    "__version__",
]
