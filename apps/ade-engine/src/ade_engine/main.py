"""CLI entrypoint for :mod:`ade_engine`.

Exposes the ADE engine runtime CLI with:

- `run`     Execute the engine for one or more inputs.
- `version` Print the engine version.
"""

from __future__ import annotations

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

import typer
from typer import BadParameter

from ade_engine import ExecutedRun, __version__
from ade_engine.engine import run_inputs
from ade_engine.settings import Settings
from ade_engine.types.run import RunStatus

app = typer.Typer(
    help=(
        "ADE engine runtime CLI.\n\n"
        "- **run** – execute the engine\n"
        "- **version** – show engine version"
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


def parse_metadata(meta: list[str]) -> dict[str, str]:
    """Parse repeated --meta=KEY=VALUE options into a dictionary."""
    result: dict[str, str] = {}

    for raw in meta:
        value = (raw or "").strip()
        if not value:
            continue

        if "=" not in value:
            raise BadParameter("--meta must be provided as KEY=VALUE", param_name="meta")

        key, val = value.split("=", 1)
        key = key.strip()
        if not key:
            raise BadParameter("Metadata key cannot be empty", param_name="meta")

        result[key] = val.strip()

    return result


def collect_input_files(
    explicit_inputs: Iterable[Path],
    input_dir: Path | None,
    include: list[str],
    exclude: list[str],
    settings: Settings,
) -> list[Path]:
    """Collect all input files from explicit paths and/or a directory scan."""
    paths = list(explicit_inputs)
    include_globs = list(dict.fromkeys((*settings.supported_file_extensions, *include)))

    if input_dir:
        for path in input_dir.rglob("*"):
            if not path.is_file():
                continue

            rel = path.relative_to(input_dir).as_posix()

            if include_globs and not any(fnmatch(rel, pat) for pat in include_globs):
                continue
            if exclude and any(fnmatch(rel, pat) for pat in exclude):
                continue

            paths.append(path)

    # De-duplicate and sort for deterministic behavior.
    return sorted(set(paths))


def print_text_summary(reports: Iterable[ExecutedRun]) -> None:
    """Print a concise, human-friendly summary for one or more runs."""
    typer.echo("Run summary:")

    for report in reports:
        result = report.result
        status = result.status.value if isinstance(result.status, RunStatus) else str(result.status)

        parts: list[str] = [status, str(report.input_file)]

        output_path = result.output_path or report.output_file
        if output_path:
            parts.append(f"output={output_path}")
        if report.logs_file:
            parts.append(f"logs={report.logs_file}")

        if result.error is not None:
            if result.error.stage:
                parts.append(f"stage={result.error.stage}")
            message = (result.error.message or "").replace("\n", " ").strip()
            parts.append(f"{result.error.code.value}: {message}")

        typer.echo(" | ".join(parts))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("run")
def run_command(
    inputs: list[Path] = typer.Option(
        [],
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Input file(s). Repeatable; may be combined with --input-dir.",
    ),
    input_dir: Path | None = typer.Option(
        None,
        "--input-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Recurse this directory for input files; may be combined with --input.",
    ),
    include: list[str] = typer.Option(
        [],
        "--include",
        help=(
            "Extra glob patterns for --input-dir (defaults already include supported extensions). "
            "Examples: --include '*.xls', --include 'receipts/**', --include '*_raw.*'."
        ),
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        help="Glob pattern(s) for files under --input-dir to exclude.",
    ),
    input_sheet: list[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for generated outputs.",
    ),
    logs_dir: Path | None = typer.Option(
        None,
        "--logs-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for per-run log files.",
    ),
    log_format: LogFormat = typer.Option(
        LogFormat.text,
        "--log-format",
        case_sensitive=False,
        help="Log output format.",
    ),
    meta: list[str] = typer.Option(
        [],
        "--meta",
        help="Extra metadata KEY=VALUE to attach to all events. Repeatable.",
    ),
    config_package: str | None = typer.Option(
        None,
        "--config-package",
        help=(
            "Config package to load (module name) or path to a config package directory. "
            f"Defaults to {Settings.config_package!r}."
        ),
    ),
) -> None:
    """Execute the engine for one or more inputs."""

    if (include or exclude) and not input_dir:
        raise BadParameter("--include/--exclude require --input-dir.", param_name="input_dir")

    settings = Settings()
    all_inputs = collect_input_files(inputs, input_dir, include, exclude, settings)
    if not all_inputs:
        raise BadParameter("No inputs found. Provide --input and/or --input-dir.")

    metadata = parse_metadata(meta)

    executed = run_inputs(
        all_inputs,
        config_package=config_package or settings.config_package,
        output_dir=output_dir,
        logs_dir=logs_dir,
        log_format=log_format.value,
        input_sheets=input_sheet or None,
        metadata=metadata,
    )

    any_failed = any(report.result.status != RunStatus.SUCCEEDED for report in executed)

    if log_format is LogFormat.text:
        print_text_summary(executed)

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
