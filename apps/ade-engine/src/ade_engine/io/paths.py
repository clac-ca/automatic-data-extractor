"""Request normalization and output path planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ade_engine.exceptions import InputError
from ade_engine.types.run import RunRequest


@dataclass(frozen=True)
class PreparedRun:
    request: RunRequest
    output_dir: Path
    output_file: Path
    logs_dir: Path | None
    logs_file: Path | None


def prepare_run_request(request: RunRequest) -> PreparedRun:
    """Normalize paths, applying defaults for output/log destinations."""

    if request.config_package is None:
        raise InputError("RunRequest must include config_package (path to config package directory)")
    if request.input_file is None:
        raise InputError("RunRequest must include input_file")
    if request.output_dir is None:
        raise InputError("RunRequest must include output_dir")

    config_package = Path(request.config_package).resolve()
    input_file = Path(request.input_file).resolve()
    output_dir = Path(request.output_dir).resolve()

    if request.output_file:
        output_file = (output_dir / request.output_file if not Path(request.output_file).is_absolute() else Path(request.output_file)).resolve()
    else:
        output_file = (output_dir / f"{input_file.stem}_normalized.xlsx").resolve()

    logs_dir = Path(request.logs_dir).resolve() if request.logs_dir else None
    if request.logs_file:
        logs_file = (
            Path(request.logs_file).resolve()
            if Path(request.logs_file).is_absolute()
            else (logs_dir / request.logs_file).resolve() if logs_dir else Path(request.logs_file).resolve()
        )
    else:
        logs_file = None

    normalized = RunRequest(
        config_package=config_package,
        manifest_path=None,
        input_file=input_file,
        input_sheets=list(request.input_sheets) if request.input_sheets else None,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
    )

    return PreparedRun(
        request=normalized,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
    )


__all__ = ["PreparedRun", "prepare_run_request"]
