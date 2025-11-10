"""ade_engine runtime package scaffold."""

from __future__ import annotations

from importlib import metadata as _metadata

from .model import EngineMetadata
from .runtime import ManifestNotFoundError, load_config_manifest

try:  # pragma: no cover - executed when package metadata is available
    __version__ = _metadata.version("ade-engine")
except _metadata.PackageNotFoundError:  # pragma: no cover - local source tree fallback
    __version__ = "0.0.0"

DEFAULT_METADATA = EngineMetadata(version=__version__)

__all__ = [
    "DEFAULT_METADATA",
    "EngineMetadata",
    "ManifestNotFoundError",
    "__version__",
    "load_config_manifest",
]
