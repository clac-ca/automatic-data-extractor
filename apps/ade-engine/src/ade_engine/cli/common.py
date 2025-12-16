"""Shared helpers/options for the ADE CLI.

Keep this module dependency-light; it should be safe to import from any CLI command module.
"""

from __future__ import annotations

import fnmatch
import logging
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import typer
from typer import BadParameter

from ade_engine.infrastructure.settings import Settings


class LogFormat(str, Enum):
    """Supported log output formats."""

    text = "text"
    ndjson = "ndjson"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def resolve_log_level(log_level: Optional[str], default_level: int) -> int:
    """Resolve a string log level to a logging level constant."""
    if not log_level:
        return default_level

    mapping = logging.getLevelNamesMapping()
    resolved = mapping.get(str(log_level).upper())
    if isinstance(resolved, int):
        return resolved

    raise BadParameter(f"Invalid log level: {log_level}", param_hint="log_level")


def resolve_logging(
    *,
    log_format: Optional[LogFormat],
    log_level: Optional[str],
    debug: bool,
    quiet: bool,
    settings: Settings,
) -> tuple[str, int]:
    """Compute effective log format/level with explicit precedence.

    Precedence: --quiet > --debug > --log-level > defaults.
    """
    effective_format = log_format.value if log_format else settings.log_format
    base_level = resolve_log_level(log_level, settings.log_level)

    if quiet:
        effective_level = logging.WARNING
    elif debug:
        effective_level = logging.DEBUG
    else:
        effective_level = base_level

    return effective_format, effective_level


# ---------------------------------------------------------------------------
# Config package resolution
# ---------------------------------------------------------------------------


def resolve_config_package(config_package: Optional[Path], settings: Settings) -> Path:
    """Resolve config package from CLI option or settings/env.

    Resolution order:
    1) explicit --config-package
    2) Settings.config_package (env var ADE_ENGINE_CONFIG_PACKAGE, settings.toml, etc.)

    Raises BadParameter if no config package is available or the path is invalid.
    """
    candidate: Optional[Path] = None
    if config_package is not None:
        candidate = Path(config_package)
    elif settings.config_package:
        candidate = Path(settings.config_package)

    if candidate is None:
        raise BadParameter(
            "Missing config package. Provide --config-package or set ADE_ENGINE_CONFIG_PACKAGE / settings.toml.",
            param_hint="config_package",
        )

    candidate = candidate.expanduser().resolve()
    if not candidate.exists():
        raise BadParameter(f"Config package not found: {candidate}", param_hint="config_package")
    if candidate.is_file():
        raise BadParameter("Config package path must be a directory", param_hint="config_package")
    return candidate


# ---------------------------------------------------------------------------
# Batch file discovery
# ---------------------------------------------------------------------------


def collect_input_files(
    *,
    input_dir: Path,
    include: Sequence[str],
    exclude: Sequence[str],
    explicit_inputs: Iterable[Path] = (),
    settings: Settings,
) -> List[Path]:
    """Collect input files for batch processing.

    Behavior:
    - Recursively scans ``input_dir`` for files with supported extensions.
    - If ``include`` patterns are provided, only keep files matching at least one include pattern.
    - ``exclude`` patterns remove matches recursively.
    - Patterns are matched against BOTH:
        - the relative path from ``input_dir`` (POSIX style), and
        - the file name.
      This makes patterns like ``*.xlsx`` work regardless of nesting.
    - ``explicit_inputs`` are always included as-is (power-user escape hatch).
    """

    input_dir = input_dir.expanduser().resolve()

    include_globs = list(dict.fromkeys(include))
    exclude_globs = list(dict.fromkeys(exclude))
    explicit_set = {p.expanduser().resolve() for p in explicit_inputs}

    supported_extensions = {
        ext.lower() if ext.startswith(".") else f".{ext.lower().lstrip('*.')}"
        for ext in settings.supported_file_extensions
        if ext
    }

    def _is_supported(path: Path) -> bool:
        return not supported_extensions or path.suffix.lower() in supported_extensions

    def _matches(path: Path, patterns: Sequence[str]) -> bool:
        rel = path.relative_to(input_dir).as_posix()
        return any(
            fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern)
            for pattern in patterns
        )

    discovered: set[Path] = set()
    for candidate in input_dir.rglob("*"):
        if not candidate.is_file():
            continue
        if not _is_supported(candidate):
            continue
        discovered.add(candidate.resolve())

    if include_globs:
        discovered = {p for p in discovered if _matches(p, include_globs)}

    if exclude_globs:
        discovered = {p for p in discovered if not _matches(p, exclude_globs)}

    return sorted(discovered | explicit_set)


# ---------------------------------------------------------------------------
# Common reusable Typer options (optional convenience)
# ---------------------------------------------------------------------------

CONFIG_PACKAGE_OPTION = typer.Option(
    None,
    "--config-package",
    file_okay=False,
    dir_okay=True,
    resolve_path=True,
    help="Path to the config package directory (or set ADE_ENGINE_CONFIG_PACKAGE / settings.toml).",
)

LOGS_DIR_OPTION = typer.Option(
    None,
    "--logs-dir",
    file_okay=False,
    dir_okay=True,
    resolve_path=True,
    help="Directory for per-run log files (default: alongside outputs).",
)

LOG_FORMAT_OPTION = typer.Option(
    None,
    "--log-format",
    case_sensitive=False,
    help="Log output format.",
)

LOG_LEVEL_OPTION = typer.Option(
    None,
    "--log-level",
    case_sensitive=False,
    help="Log level (debug, info, warning, error, critical).",
)

DEBUG_OPTION = typer.Option(
    False,
    "--debug",
    help="Enable debug logging and verbose diagnostics.",
)

QUIET_OPTION = typer.Option(
    False,
    "--quiet",
    help="Reduce output to warnings and errors.",
)


__all__ = [
    "LogFormat",
    "collect_input_files",
    "resolve_config_package",
    "resolve_logging",
    "CONFIG_PACKAGE_OPTION",
    "LOGS_DIR_OPTION",
    "LOG_FORMAT_OPTION",
    "LOG_LEVEL_OPTION",
    "DEBUG_OPTION",
    "QUIET_OPTION",
]
