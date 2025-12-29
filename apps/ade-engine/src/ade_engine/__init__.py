"""Public API for :mod:`ade_engine`."""

from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING
import tomllib

if TYPE_CHECKING:
    from ade_engine.application.engine import Engine
    from ade_engine.infrastructure.settings import Settings
    from ade_engine.models import FieldDef, HookName, RowKind
    from ade_engine.models.run import RunRequest, RunResult, RunStatus

def _pyproject_version() -> str | None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        version = parsed.get("project", {}).get("version")
        if isinstance(version, str) and version:
            return version
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return None
    return None


def _resolve_version() -> str:
    # Prefer the local pyproject when running from a source checkout/editable install.
    version = _pyproject_version()
    if version is not None:
        return version

    try:
        return metadata.version("ade-engine")
    except metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


__version__ = _resolve_version()

_EXPORTS = {
    "Engine": ("ade_engine.application.engine", "Engine"),
    "Settings": ("ade_engine.infrastructure.settings", "Settings"),
    "FieldDef": ("ade_engine.models", "FieldDef"),
    "HookName": ("ade_engine.models", "HookName"),
    "RowKind": ("ade_engine.models", "RowKind"),
    "RunRequest": ("ade_engine.models.run", "RunRequest"),
    "RunResult": ("ade_engine.models.run", "RunResult"),
    "RunStatus": ("ade_engine.models.run", "RunStatus"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))


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
