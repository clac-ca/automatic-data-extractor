"""Request normalization and output path planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ade_engine.config.loader import ResolvedConfigPackage, resolve_config_package
from ade_engine.exceptions import InputError
from ade_engine.types.run import RunRequest


@dataclass(frozen=True)
class PreparedRun:
    """Resolved inputs/outputs for a run request."""

    request: RunRequest
    resolved_config: ResolvedConfigPackage
    output_dir: Path
    output_file: Path
    logs_dir: Path | None
    logs_file: Path | None
    config_sys_path: Path | None


def prepare_run_request(request: RunRequest, *, default_config_package: str | None = None) -> PreparedRun:
    """Normalize paths, resolve config package, and fill defaults."""

    resolved_config = resolve_config_package(request.config_package or default_config_package)

    if request.input_file is None:
        raise InputError("RunRequest must include input_file")

    input_file = Path(request.input_file).resolve()

    output_dir = Path(request.output_dir).resolve() if request.output_dir else (input_file.parent / "output")
    output_file = Path(request.output_file).resolve() if request.output_file else (output_dir / "normalized.xlsx")

    logs_dir = Path(request.logs_dir).resolve() if request.logs_dir else None
    logs_file = (
        Path(request.logs_file).resolve()
        if request.logs_file
        else (logs_dir / "engine_events.ndjson" if logs_dir else None)
    )

    normalized = RunRequest(
        run_id=request.run_id,
        config_package=resolved_config.package,
        manifest_path=Path(request.manifest_path).resolve() if request.manifest_path else None,
        input_file=input_file,
        input_sheets=list(request.input_sheets) if request.input_sheets else None,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
        metadata=dict(request.metadata or {}),
    )

    return PreparedRun(
        request=normalized,
        resolved_config=resolved_config,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
        config_sys_path=resolved_config.sys_path,
    )


__all__ = ["PreparedRun", "prepare_run_request"]
