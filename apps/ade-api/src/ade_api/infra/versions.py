"""Helpers for reading installed package versions."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["installed_version"]


def installed_version(*dist_names: str) -> str:
    """Return the first installed distribution version or ``unknown``."""

    for name in dist_names:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return "unknown"
