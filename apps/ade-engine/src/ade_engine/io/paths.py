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
    """Normalize paths, resolve the config package, and fill defaults.

    Rules:
    - ``input_file`` is required.
    - ``output_dir`` is required; callers decide where artifacts live.
    - If ``output_file`` is omitted, it defaults to ``<input_stem>_normalized.xlsx`` under ``output_dir``.
    - If ``output_file`` is provided as a bare filename, it is treated as relative to ``output_dir``.
    - If ``logs_file`` is provided as a bare filename, it is treated as relative to ``logs_dir``.
    """

    resolved_config = resolve_config_package(request.config_package or default_config_package)

    if request.input_file is None:
        raise InputError("RunRequest must include input_file")

    if request.output_dir is None:
        raise InputError("RunRequest must include output_dir")

    input_file = Path(request.input_file).resolve()
    output_dir = Path(request.output_dir).resolve()

    if request.output_file:
        candidate = Path(request.output_file)
        if not candidate.is_absolute() and candidate.parent == Path("."):
            candidate = output_dir / candidate
        output_file = candidate.resolve()
    else:
        output_file = (output_dir / f"{input_file.stem}_normalized.xlsx").resolve()

    logs_dir = Path(request.logs_dir).resolve() if request.logs_dir else None
    if request.logs_file:
        candidate = Path(request.logs_file)
        if logs_dir and not candidate.is_absolute() and candidate.parent == Path("."):
            candidate = logs_dir / candidate
        logs_file = candidate.resolve()
    else:
        logs_file = None

    normalized = RunRequest(
        config_package=resolved_config.package,
        manifest_path=Path(request.manifest_path).resolve() if request.manifest_path else None,
        input_file=input_file,
        input_sheets=list(request.input_sheets) if request.input_sheets else None,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
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
