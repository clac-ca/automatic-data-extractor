"""Helpers for working with virtual environments.

This module centralizes platform-specific venv path conventions (bin/Scripts)
so callers don't re-implement them in multiple places.
"""

from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Mapping

__all__ = [
    "venv_bin_dir",
    "venv_bin_path",
    "venv_python_path",
    "pip_install_env",
    "apply_venv_to_env",
]


def venv_bin_dir() -> str:
    """Return the platform bin directory for virtual environments."""
    return "Scripts" if os.name == "nt" else "bin"


def venv_bin_path(venv_path: Path) -> Path:
    """Return the bin directory inside a virtual environment."""
    return venv_path / venv_bin_dir()


def venv_python_path(venv_path: Path, *, must_exist: bool = True) -> Path:
    """Return the Python interpreter inside a virtual environment.

    Parameters
    ----------
    venv_path:
        The root directory of the venv (the folder that contains bin/Scripts).
    must_exist:
        When true, raise FileNotFoundError if the interpreter does not exist.
    """
    executable = "python.exe" if os.name == "nt" else "python"
    candidate = venv_bin_path(venv_path) / executable
    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"Python interpreter not found in {venv_path}")
    return candidate


def pip_install_env(pip_cache_dir: Path | None) -> dict[str, str]:
    """Environment variables used for non-interactive pip installs."""
    if pip_cache_dir is None:
        return {}
    return {
        "PIP_NO_INPUT": "1",
        "PIP_CACHE_DIR": str(pip_cache_dir),
    }


def apply_venv_to_env(env: Mapping[str, str], venv_path: Path) -> dict[str, str]:
    """Return a copy of ``env`` with venv activation variables applied.

    This does not 'activate' the shell; it just ensures spawned subprocesses use
    the venv by default by setting VIRTUAL_ENV and prefixing PATH.
    """
    merged = dict(env)
    bin_path = venv_bin_path(venv_path)
    merged["VIRTUAL_ENV"] = str(venv_path)
    merged["PATH"] = os.pathsep.join([str(bin_path), merged.get("PATH", "")])
    return merged
