"""CLI entrypoint for :mod:`ade_engine`.

Exposes the ADE engine runtime CLI with:

- `run`     Execute the engine for one or more inputs.
- `version` Print the engine version.
"""

from __future__ import annotations

import logging
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Optional

import typer
from typer import BadParameter

from ade_engine import __version__
from ade_engine.engine import run_inputs
from ade_engine.settings import Settings
from ade_engine.types.run import RunStatus

app = typer.Typer(
    help=(
        "ADE engine runtime CLI.\n\n"
        "- **run** - execute the engine\n"
        "- **version** - show engine version"
    ),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

class LogFormat(str, Enum):
    """Supported log output formats."""

    text = "text"
    ndjson = "ndjson"


# ---------------------------------------------------------------------------
# Helpers
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


def collect_input_files(
    explicit_inputs: Iterable[Path],
    input_dir: Optional[Path],
    include: List[str],
    exclude: List[str],
    settings: Settings,
) -> List[Path]:
    """Collect all input files from explicit paths and/or a directory scan."""
    paths = list(explicit_inputs)
    include_globs = list(dict.fromkeys(include))
    supported_extensions = {
        ext.lower() if ext.startswith(".") else f".{ext.lower().lstrip('*.')}"
        for ext in settings.supported_file_extensions
        if ext
    }

    if input_dir:
        for path in input_dir.rglob("*"):
            if not path.is_file():
                continue

            rel = path.relative_to(input_dir).as_posix()

            matches_include = bool(include_globs) and any(fnmatch(rel, pat) for pat in include_globs)
            matches_default_ext = not supported_extensions or path.suffix.lower() in supported_extensions

            if not matches_default_ext and not matches_include:
                continue
            if exclude and any(fnmatch(rel, pat) for pat in exclude):
                continue

            paths.append(path)

    # De-duplicate and sort for deterministic behavior.
    return sorted(set(paths))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("run")
def run_command(
    inputs: List[Path] = typer.Option(
        [],
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Input file(s). Repeatable; may be combined with --input-dir.",
    ),
    input_dir: Optional[Path] = typer.Option(
        None,
        "--input-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Recurse this directory for input files; may be combined with --input.",
    ),
    include: List[str] = typer.Option(
        [],
        "--include",
        help=(
            "Extra glob patterns for --input-dir (defaults already include supported extensions). "
            "Examples: --include '*.xls', --include 'receipts/**', --include '*_raw.*'."
        ),
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        help="Glob pattern(s) for files under --input-dir to exclude.",
    ),
    input_sheet: List[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for generated outputs.",
    ),
    logs_dir: Optional[Path] = typer.Option(
        None,
        "--logs-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for per-run log files.",
    ),
    log_format: Optional[LogFormat] = typer.Option(
        None,
        "--log-format",
        case_sensitive=False,
        help="Log output format.",
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        case_sensitive=False,
        help="Log level (debug, info, warning, error, critical).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging and verbose diagnostics.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Reduce output to warnings and errors.",
    ),
    config_package: Path = typer.Option(
        ...,
        "--config-package",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Path to the config package directory (e.g., <workspace>/config_packages/<id>/src/ade_config or its root).",
    ),
) -> None:
    """Execute the engine for one or more inputs."""

    if (include or exclude) and not input_dir:
        raise BadParameter("--include/--exclude require --input-dir.", param_hint="input_dir")

    settings = Settings()
    all_inputs = collect_input_files(inputs, input_dir, include, exclude, settings)
    if not all_inputs:
        raise BadParameter("No inputs found. Provide --input and/or --input-dir.")

    effective_log_format = log_format.value if log_format else settings.log_format

    effective_log_level = resolve_log_level(log_level, settings.log_level)
    if debug:
        effective_log_level = logging.DEBUG
    if quiet:
        effective_log_level = logging.WARNING

    executed = run_inputs(
        all_inputs,
        config_package=config_package,
        output_dir=output_dir,
        logs_dir=logs_dir,
        log_format=effective_log_format,
        log_level=effective_log_level,
        input_sheets=input_sheet or None,
    )

    any_failed = any(report.result.status != RunStatus.SUCCEEDED for report in executed)

    raise typer.Exit(code=1 if any_failed else 0)


@app.command("version")
def version_command() -> None:
    """Print the engine version."""
    typer.echo(__version__)


# ---------------------------------------------------------------------------
# Module entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Entrypoint used by console scripts and `python -m ade_engine`."""
    app()


__all__ = ["app", "main"]
