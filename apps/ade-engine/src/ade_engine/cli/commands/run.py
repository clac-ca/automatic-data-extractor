"""`ade-engine run` command implementation."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import UUID

import typer

from ade_engine import Engine, RunRequest, RunResult
from ade_engine.core.types import RunStatus
from ade_engine.infra.telemetry import EventSink, TelemetryConfig
from ade_engine.schemas import EngineEventFrameV1, RunSummary

DEFAULT_INCLUDE_PATTERNS = ("*.xlsx", "*.csv")


@dataclass
class RunPlan:
    input_file: Path
    output_dir: Path
    output_file: Path
    logs_dir: Path | None
    logs_file: Path | None


@dataclass
class RunCapture:
    input_file: Path
    output_dir: Path
    output_file: Path
    logs_dir: Path | None
    logs_file: Path | None
    run_id: UUID | None = None
    summary: RunSummary | None = None
    result: RunResult | None = None


class _NullEventSink:
    def emit(self, _: EngineEventFrameV1) -> None:
        return None


class _CaptureSink:
    """Capture run summaries while allowing other sinks to stream events."""

    def __init__(self, capture: RunCapture) -> None:
        self.capture = capture

    def emit(self, frame: EngineEventFrameV1) -> None:
        if frame.type == "engine.run.summary":
            try:
                self.capture.summary = RunSummary.model_validate(frame.payload)
            except Exception:
                pass
        return None


def _collect_inputs(
    explicit_inputs: Iterable[Path],
    input_dir: Path | None,
    include: list[str],
    exclude: list[str],
) -> list[Path]:
    candidates = [path.resolve() for path in explicit_inputs]
    include_patterns = include or list(DEFAULT_INCLUDE_PATTERNS)

    if input_dir:
        root = input_dir.resolve()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if include_patterns and not any(fnmatch(relative, pattern) for pattern in include_patterns):
                continue
            if exclude and any(fnmatch(relative, pattern) for pattern in exclude):
                continue
            candidates.append(path.resolve())

    unique_inputs = sorted({path for path in candidates})
    return unique_inputs


def _plan_runs(
    inputs: list[Path],
    *,
    output_dir: Path | None,
    output_file: Path | None,
    logs_dir: Path | None,
    logs_file: Path | None,
) -> list[RunPlan]:
    multiple_inputs = len(inputs) > 1
    plans: list[RunPlan] = []

    for input_file in inputs:
        base_output_dir = output_dir
        if base_output_dir and multiple_inputs:
            base_output_dir = base_output_dir / input_file.stem
        resolved_output_dir = base_output_dir or input_file.parent / "output"

        resolved_output_file = output_file or (resolved_output_dir / "normalized.xlsx")

        base_logs_dir = logs_dir
        if base_logs_dir and multiple_inputs:
            base_logs_dir = base_logs_dir / input_file.stem
        resolved_logs_dir = base_logs_dir
        resolved_logs_file = logs_file or (base_logs_dir / "engine_events.ndjson" if base_logs_dir else None)

        plans.append(
            RunPlan(
                input_file=input_file,
                output_dir=resolved_output_dir,
                output_file=resolved_output_file,
                logs_dir=resolved_logs_dir,
                logs_file=resolved_logs_file,
            )
        )
    return plans


def _build_telemetry(quiet: bool, format: str, captures: list[RunCapture]) -> TelemetryConfig:
    suppress_stdout = quiet or format.lower() == "json"

    def _capture_factory(run_ctx) -> EventSink:
        capture = RunCapture(
            input_file=run_ctx.paths.input_file,
            output_dir=run_ctx.paths.output_dir,
            output_file=run_ctx.paths.output_file,
            logs_dir=run_ctx.paths.logs_dir,
            logs_file=run_ctx.paths.logs_file,
            run_id=run_ctx.run_id,
        )
        captures.append(capture)
        return _CaptureSink(capture)

    stdout_sink_factory = (lambda _run: _NullEventSink()) if suppress_stdout else None
    return TelemetryConfig(event_sink_factories=[_capture_factory], stdout_sink_factory=stdout_sink_factory)


def _mapped_fields(summary: RunSummary | None) -> list[str]:
    if summary is None:
        return []
    return [field.field for field in summary.fields if field.mapped]


def _run_payload(report: RunCapture) -> dict[str, Any]:
    result = report.result
    status_value = result.status.value if isinstance(result.status, RunStatus) else str(result.status)
    mapped_fields = _mapped_fields(report.summary)
    error = None
    if result.error:
        error = {
            "code": getattr(result.error, "code", None).value if getattr(result.error, "code", None) else None,
            "stage": getattr(result.error, "stage", None).value if getattr(result.error, "stage", None) else None,
            "message": getattr(result.error, "message", None),
        }
        error = {k: v for k, v in (error or {}).items() if v is not None}
    payload: dict[str, Any] = {
        "input_file": str(report.input_file),
        "status": status_value,
        "run_id": str(result.run_id),
        "output_dir": str(report.output_dir) if report.output_dir else None,
        "output_file": str(report.output_file) if report.output_file else None,
        "logs_file": str(report.logs_file) if report.logs_file else None,
        "logs_dir": str(report.logs_dir) if report.logs_dir else None,
        "processed_file": str(result.processed_file) if result.processed_file else None,
        "fields_mapped": mapped_fields,
        "fields_mapped_count": len(mapped_fields),
    }
    if error:
        payload["error"] = error
    if report.summary:
        payload["counts"] = report.summary.counts.model_dump()
    return payload


def _aggregate_payload(reports: list[RunCapture]) -> dict[str, Any]:
    totals = Counter()
    field_frequency: Counter[str] = Counter()
    runs_payload = []
    for report in reports:
        if report.result is None:
            continue
        totals["runs"] += 1
        status_value = report.result.status.value if isinstance(report.result.status, RunStatus) else str(report.result.status)
        totals[status_value] += 1
        mapped_fields = _mapped_fields(report.summary)
        field_frequency.update(mapped_fields)
        runs_payload.append(_run_payload(report))

    aggregate = {
        "runs": runs_payload,
        "totals": {
            "runs": totals.get("runs", 0),
            "succeeded": totals.get(RunStatus.SUCCEEDED.value, totals.get("succeeded", 0)),
            "failed": totals.get(RunStatus.FAILED.value, totals.get("failed", 0)),
        },
        "field_frequency": dict(sorted(field_frequency.items())),
    }
    return aggregate


def _print_text_summary(reports: list[RunCapture], *, include_aggregate: bool) -> None:
    typer.echo("")
    typer.echo("Run summary:")
    for report in reports:
        if report.result is None:
            continue
        status_value = report.result.status.value if isinstance(report.result.status, RunStatus) else str(report.result.status)
        mapped_fields = _mapped_fields(report.summary)
        mapped_fragment = f"mapped {len(mapped_fields)} fields" if mapped_fields else "mapped 0 fields"
        if mapped_fields:
            mapped_fragment += f" ({', '.join(mapped_fields)})"
        typer.echo(
            f"- {report.input_file}: {status_value} | output: {report.output_file} | logs: "
            f"{report.logs_file or report.logs_dir or 'stdout only'} | {mapped_fragment}"
        )

    if include_aggregate:
        aggregate = _aggregate_payload(reports)
        totals = aggregate["totals"]
        field_freq = aggregate["field_frequency"]
        typer.echo("")
        typer.echo(
            f"Aggregate: runs={totals.get('runs', 0)}, "
            f"succeeded={totals.get('succeeded', 0)}, failed={totals.get('failed', 0)}"
        )
        if field_freq:
            freq_parts = [f"{name}={count}" for name, count in field_freq.items()]
            typer.echo(f"Field frequency: {', '.join(freq_parts)}")


def run_command(
    input: list[Path] = typer.Option(
        [],
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Source file(s) (repeatable). May be combined with --input-dir.",
    ),
    input_dir: Optional[Path] = typer.Option(
        None,
        "--input-dir",
        file_okay=False,
        dir_okay=True,
        exists=True,
        help="Recurse a directory of inputs. May be combined with --input.",
    ),
    include: list[str] = typer.Option(
        [],
        "--include",
        help="Glob applied under --input-dir (default: *.xlsx, *.csv).",
    ),
    exclude: list[str] = typer.Option(
        [],
        "--exclude",
        help="Glob to skip under --input-dir.",
    ),
    input_sheet: list[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True),
    output_file: Optional[Path] = typer.Option(None, "--output-file", file_okay=True, dir_okay=False),
    logs_dir: Optional[Path] = typer.Option(
        None,
        "--logs-dir",
        file_okay=False,
        dir_okay=True,
        help="Directory for NDJSON events (default: stdout only).",
    ),
    logs_file: Optional[Path] = typer.Option(
        None,
        "--logs-file",
        file_okay=True,
        dir_okay=False,
        help="Explicit NDJSON events file (disables stdout-only).",
    ),
    config_package: str = typer.Option(
        "ade_config",
        "--config-package",
        help="Config package to load (module name) or path to a config package directory.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet/--no-quiet",
        help="Suppress per-run NDJSON on stdout; still write logs if set.",
    ),
    format: str = typer.Option(
        "text",
        "--format",
        case_sensitive=False,
        help="stdout format (default text).",
    ),
    aggregate_summary: bool = typer.Option(
        False,
        "--aggregate-summary",
        help="Print aggregate summary across inputs.",
    ),
    aggregate_summary_file: Optional[Path] = typer.Option(
        None,
        "--aggregate-summary-file",
        file_okay=True,
        dir_okay=False,
        help="Write aggregate summary JSON to this path.",
    ),
) -> None:
    """Execute the engine for one or more inputs.

    Inputs from --input/--input-dir are merged, de-duplicated, and sorted.
    """

    if include and not input_dir:
        raise typer.BadParameter("--include requires --input-dir.")
    if exclude and not input_dir:
        raise typer.BadParameter("--exclude requires --input-dir.")

    normalized_format = format.lower()
    if normalized_format not in {"text", "json"}:
        raise typer.BadParameter("--format must be one of: text, json")

    inputs = _collect_inputs(input, input_dir, include, exclude)
    if not inputs:
        raise typer.BadParameter("Provide --input and/or --input-dir (no inputs found).")

    plans = _plan_runs(
        inputs,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
    )

    captures: list[RunCapture] = []
    telemetry = _build_telemetry(quiet=quiet, format=normalized_format, captures=captures)
    engine = Engine(telemetry=telemetry)

    exit_code = 0
    for plan in plans:
        request = RunRequest(
            config_package=config_package,
            input_file=plan.input_file,
            input_sheets=list(input_sheet) if input_sheet else None,
            output_dir=plan.output_dir,
            output_file=plan.output_file,
            logs_dir=plan.logs_dir,
            logs_file=plan.logs_file,
        )
        result = engine.run(request)
        matched_capture = next((cap for cap in captures if cap.run_id == result.run_id), None)
        if matched_capture:
            matched_capture.result = result
        if result.status != RunStatus.SUCCEEDED:
            exit_code = 1

    # Build summaries after runs complete to avoid interleaving with NDJSON streams.
    reports = [capture for capture in captures if capture.result is not None]
    aggregate_payload = _aggregate_payload(reports) if reports else {"runs": [], "totals": {}, "field_frequency": {}}

    if aggregate_summary_file:
        aggregate_summary_file.parent.mkdir(parents=True, exist_ok=True)
        with aggregate_summary_file.open("w", encoding="utf-8") as handle:
            json.dump(aggregate_payload, handle, indent=2)

    if normalized_format == "json":
        if aggregate_summary:
            typer.echo(json.dumps(aggregate_payload))
        else:
            for report in reports:
                typer.echo(json.dumps(_run_payload(report)))
    else:
        _print_text_summary(reports, include_aggregate=aggregate_summary)

    raise typer.Exit(code=exit_code)


__all__ = ["run_command"]
