"""`ade-engine run` command implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ade_engine import Engine, RunRequest


def _parse_metadata(values: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise typer.BadParameter("Metadata entries must be in key=value format")
        key, value = item.split("=", 1)
        metadata[key] = value
    return metadata


def run_command(
    input: list[Path] = typer.Option(
        [],
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Source file to process (repeatable).",
    ),
    input_sheet: list[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True),
    output_file: Optional[Path] = typer.Option(None, "--output-file", file_okay=True, dir_okay=False),
    events_dir: Optional[Path] = typer.Option(
        None,
        "--events-dir",
        "--logs-dir",
        file_okay=False,
        dir_okay=True,
        help="Directory for engine NDJSON events (no file sink unless provided).",
    ),
    events_file: Optional[Path] = typer.Option(
        None,
        "--events-file",
        file_okay=True,
        dir_okay=False,
        help="Explicit file path for engine NDJSON events (disables stdout-only).",
    ),
    config_package: str = typer.Option(
        "ade_config",
        "--config-package",
        help="Config package to load (module name) or path to a config package directory.",
    ),
    metadata: list[str] = typer.Option([], "--metadata"),
) -> None:
    """Execute the engine once and print a JSON summary."""

    if not input:
        raise typer.BadParameter("At least one --input is required")

    exit_code = 0
    multiple_inputs = len(input) > 1
    for input_file in input:
        base_output_dir = output_dir
        if base_output_dir and multiple_inputs:
            base_output_dir = base_output_dir / input_file.stem
        resolved_output_dir = base_output_dir or input_file.parent / "output"

        resolved_output_file = output_file
        if resolved_output_file is None:
            resolved_output_file = resolved_output_dir / "normalized.xlsx"

        base_events_dir = events_dir
        if base_events_dir and multiple_inputs:
            base_events_dir = base_events_dir / input_file.stem

        resolved_events_file = events_file
        resolved_events_dir = base_events_dir
        if resolved_events_file is None and base_events_dir is not None:
            resolved_events_file = base_events_dir / "engine_events.ndjson"

        request = RunRequest(
            config_package=config_package,
            input_file=input_file,
            input_sheets=list(input_sheet) if input_sheet else None,
            output_dir=resolved_output_dir,
            output_file=resolved_output_file,
            events_dir=resolved_events_dir,
            events_file=resolved_events_file,
            metadata=_parse_metadata(metadata) if metadata else None,
        )

        result = Engine().run(request)
        if result.status is not result.status.SUCCEEDED:
            exit_code = 1

    raise typer.Exit(code=exit_code)


__all__ = ["run_command"]
