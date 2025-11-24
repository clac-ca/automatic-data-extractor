"""`ade-engine run` command implementation."""

from __future__ import annotations

import json
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
    input: Optional[Path] = typer.Option(None, "--input", exists=True, file_okay=True, dir_okay=False),
    input_dir: Optional[Path] = typer.Option(None, "--input-dir", exists=True, file_okay=False, dir_okay=True),
    input_sheet: list[str] = typer.Option([], "--input-sheet"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True),
    logs_dir: Optional[Path] = typer.Option(None, "--logs-dir", file_okay=False, dir_okay=True),
    config_package: str = typer.Option("ade_config", "--config-package"),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path", exists=True, file_okay=True, dir_okay=False),
    metadata: list[str] = typer.Option([], "--metadata"),
) -> None:
    """Execute the engine once and print a JSON summary."""

    request = RunRequest(
        config_package=config_package,
        manifest_path=manifest_path,
        input_files=[input] if input else None,
        input_dir=input_dir,
        input_sheets=input_sheet or None,
        output_dir=output_dir,
        logs_dir=logs_dir,
        metadata=_parse_metadata(metadata) if metadata else None,
    )

    result = Engine().run(request)
    payload = {
        "status": result.status.value,
        "run_id": result.run_id,
        "output_paths": [str(path) for path in result.output_paths],
        "artifact_path": str(result.artifact_path),
        "events_path": str(result.events_path),
        "processed_files": list(result.processed_files),
    }
    if result.error:
        payload["error"] = {
            "code": result.error.code,
            "stage": result.error.stage.value if result.error.stage else None,
            "message": result.error.message,
        }

    typer.echo(json.dumps(payload))
    raise typer.Exit(code=0 if result.status is result.status.SUCCEEDED else 1)


__all__ = ["run_command"]
