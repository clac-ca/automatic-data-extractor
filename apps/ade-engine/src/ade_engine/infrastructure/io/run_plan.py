"""Run request normalization and path planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ade_engine.models.errors import InputError
from ade_engine.models.run import RunRequest


@dataclass(frozen=True)
class RunPlan:
    request: RunRequest
    output_dir: Path
    output_path: Path
    logs_dir: Path
    logs_path: Path | None


def plan_run(request: RunRequest, *, log_format: str) -> RunPlan:
    """Resolve a :class:`~ade_engine.models.run.RunRequest` into absolute paths."""

    config_package = Path(request.config_package).expanduser().resolve()
    if not config_package.exists():
        raise InputError(f"Config package path does not exist: {config_package}")
    if config_package.is_file():
        raise InputError(f"Config package path must be a directory: {config_package}")

    input_file = Path(request.input_file).expanduser().resolve()
    if not input_file.exists():
        raise InputError(f"Input file not found: {input_file}")
    if input_file.is_dir():
        raise InputError(f"Input file must be a file, not a directory: {input_file}")

    if request.output_path is not None:
        output_path = (
            request.output_path.expanduser().resolve()
            if request.output_path.is_absolute()
            else (Path.cwd() / request.output_path).expanduser().resolve()
        )
        output_dir = output_path.parent
    else:
        output_dir = (
            request.output_dir.expanduser().resolve()
            if request.output_dir is not None
            else input_file.parent
        )
        output_path = (output_dir / f"{input_file.stem}_normalized.xlsx").resolve()

    if output_path.suffix.lower() != ".xlsx":
        raise InputError(f"Output path must end with .xlsx: {output_path}")

    logs_dir = (
        request.logs_dir.expanduser().resolve()
        if request.logs_dir is not None
        else output_dir
    )

    if request.logs_path is not None:
        logs_path = (
            request.logs_path.expanduser().resolve()
            if request.logs_path.is_absolute()
            else (logs_dir / request.logs_path).expanduser().resolve()
        )
    else:
        fmt = (log_format or "text").strip().lower()
        suffix = "engine_events.ndjson" if fmt in {"ndjson", "json"} else "engine.log"
        logs_path = (logs_dir / f"{input_file.stem}_{suffix}").resolve()

    normalized = RunRequest(
        config_package=config_package,
        input_file=input_file,
        input_sheets=list(request.input_sheets) if request.input_sheets else None,
        output_dir=output_dir,
        output_path=output_path,
        logs_dir=logs_dir,
        logs_path=logs_path,
    )

    return RunPlan(
        request=normalized,
        output_dir=output_dir,
        output_path=output_path,
        logs_dir=logs_dir,
        logs_path=logs_path,
    )


__all__ = ["RunPlan", "plan_run"]
