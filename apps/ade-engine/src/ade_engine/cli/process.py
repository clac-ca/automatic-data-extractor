"""Process commands for the ADE CLI."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from typer import BadParameter

from ade_engine.engine import Engine
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunStatus

from .common import (
    LogFormat,
    CONFIG_PACKAGE_OPTION,
    DEBUG_OPTION,
    LOG_FORMAT_OPTION,
    LOG_LEVEL_OPTION,
    LOGS_DIR_OPTION,
    QUIET_OPTION,
    collect_input_files,
    resolve_config_package,
    resolve_logging,
)

app = typer.Typer(
    help=(
        "Process inputs with the ADE engine.\n\n"
        "Use `process file` for a single input, `process batch` for recursive directory runs."
    ),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


@app.command("file")
def process_file(
    input_file: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Single input file.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        resolve_path=False,
        help=(
            "Output file path. If omitted, defaults to <input_parent>/<input_stem>_normalized.xlsx"
            " unless --output-dir is provided. Must end with .xlsx."
        ),
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for generated output when --output is not provided (default: input file's directory).",
    ),
    logs_dir: Optional[Path] = LOGS_DIR_OPTION,
    input_sheet: List[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    log_format: Optional[LogFormat] = LOG_FORMAT_OPTION,
    log_level: Optional[str] = LOG_LEVEL_OPTION,
    debug: bool = DEBUG_OPTION,
    quiet: bool = QUIET_OPTION,
    config_package: Optional[Path] = CONFIG_PACKAGE_OPTION,
) -> None:
    """Process a single input file."""

    if output is not None and output_dir is not None:
        raise BadParameter("--output and --output-dir are mutually exclusive; choose one.", param_hint="output")

    bootstrap_settings = Settings.load()
    config_path = resolve_config_package(config_package, bootstrap_settings)
    settings = Settings.load(config_package_dir=config_path)
    effective_format, effective_level = resolve_logging(
        log_format=log_format,
        log_level=log_level,
        debug=debug,
        quiet=quiet,
        settings=settings,
    )

    engine_settings = settings.model_copy(update={"log_format": effective_format, "log_level": effective_level})
    engine = Engine(settings=engine_settings)

    resolved_input = input_file.resolve()
    if not resolved_input.is_file():
        raise BadParameter(f"Input file not found: {resolved_input}", param_hint="input")

    # Determine output destination
    request_output_dir: Optional[Path] = None
    request_output_path: Optional[Path] = None
    if output is not None:
        target = (Path.cwd() / output).expanduser().resolve() if not output.is_absolute() else output.expanduser().resolve()
        if target.suffix.lower() != ".xlsx":
            raise BadParameter("--output must end with .xlsx", param_hint="output")
        request_output_path = target
    elif output_dir is not None:
        request_output_dir = output_dir.expanduser().resolve()
    else:
        request_output_dir = None
        request_output_path = None

    # Logs default to the output directory unless overridden
    resolved_logs_dir = logs_dir.expanduser().resolve() if logs_dir is not None else None

    result = engine.run(
        RunRequest(
            config_package=config_path,
            input_file=resolved_input,
            input_sheets=input_sheet or None,
            output_dir=request_output_dir,
            output_path=request_output_path,
            logs_dir=resolved_logs_dir,
        )
    )

    raise typer.Exit(code=0 if result.status == RunStatus.SUCCEEDED else 1)


@app.command("batch")
def process_batch(
    input_dir: Path = typer.Option(
        ...,
        "--input-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory to scan recursively for inputs.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory for generated outputs (required).",
    ),
    include: List[str] = typer.Option(
        [],
        "--include",
        help=(
            "Optional glob patterns (relative to --input-dir) to include. "
            "If provided, only matching files are processed."
        ),
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        help="Glob pattern(s) applied recursively to skip inputs under --input-dir.",
    ),
    input_sheet: List[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest for every file; defaults to all visible sheets.",
    ),
    logs_dir: Optional[Path] = LOGS_DIR_OPTION,
    log_format: Optional[LogFormat] = LOG_FORMAT_OPTION,
    log_level: Optional[str] = LOG_LEVEL_OPTION,
    debug: bool = DEBUG_OPTION,
    quiet: bool = QUIET_OPTION,
    config_package: Optional[Path] = CONFIG_PACKAGE_OPTION,
) -> None:
    """Process a batch of files from a directory scan."""

    bootstrap_settings = Settings.load()
    config_path = resolve_config_package(config_package, bootstrap_settings)
    settings = Settings.load(config_package_dir=config_path)
    effective_format, effective_level = resolve_logging(
        log_format=log_format,
        log_level=log_level,
        debug=debug,
        quiet=quiet,
        settings=settings,
    )

    engine_settings = settings.model_copy(update={"log_format": effective_format, "log_level": effective_level})
    engine = Engine(settings=engine_settings)

    batch_inputs = collect_input_files(
        input_dir=input_dir,
        include=include,
        exclude=exclude,
        explicit_inputs=(),
        settings=settings,
    )
    if not batch_inputs:
        raise BadParameter("No inputs found under --input-dir after filters.", param_hint="input_dir")

    resolved_output_dir = output_dir.expanduser().resolve()
    resolved_logs_dir = logs_dir.expanduser().resolve() if logs_dir is not None else resolved_output_dir
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    any_failed = False
    for path in batch_inputs:
        result = engine.run(
            RunRequest(
                config_package=config_path,
                input_file=path,
                input_sheets=input_sheet or None,
                output_dir=resolved_output_dir,
                logs_dir=resolved_logs_dir,
            )
        )
        if result.status != RunStatus.SUCCEEDED:
            any_failed = True

    raise typer.Exit(code=1 if any_failed else 0)


__all__ = ["app"]
