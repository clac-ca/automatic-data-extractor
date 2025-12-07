"""CLI entrypoint for :mod:`ade_engine`."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Optional
from uuid import uuid4

import typer

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from ade_engine import ADEngine, __version__
from ade_engine.reporting import build_reporting, protect_stdout
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunResult, RunStatus

app = typer.Typer(add_completion=False, help="ADE engine runtime CLI")

_LOG_FORMATS = {"text", "ndjson"}


@dataclass(frozen=True)
class RunPlan:
    input_file: Path
    output_dir: Path
    output_file: Path
    logs_dir: Path | None
    logs_file: Path | None


@dataclass
class RunReport:
    plan: RunPlan
    result: RunResult | None = None


def collect_input_files(
    explicit_inputs: Iterable[Path],
    input_dir: Path | None,
    include: list[str],
    exclude: list[str],
    settings: Settings,
) -> list[Path]:
    paths = [path.resolve() for path in explicit_inputs]
    include_patterns = include or list(settings.include_patterns)

    if input_dir:
        root = input_dir.resolve()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if include_patterns and not any(fnmatch(rel, pattern) for pattern in include_patterns):
                continue
            if exclude and any(fnmatch(rel, pattern) for pattern in exclude):
                continue
            paths.append(path.resolve())

    return sorted(set(paths))


def default_logs_filename(log_format: str) -> str:
    return "engine_events.ndjson" if log_format == "ndjson" else "engine.log"


def plan_runs(
    inputs: list[Path],
    *,
    log_format: str,
    output_dir: Path | None,
    output_file: Path | None,
    logs_dir: Path | None,
    logs_file: Path | None,
) -> list[RunPlan]:
    multiple_inputs = len(inputs) > 1
    plans: list[RunPlan] = []

    for input_file in inputs:
        resolved_output_dir = output_dir
        if resolved_output_dir and multiple_inputs:
            resolved_output_dir = resolved_output_dir / input_file.stem
        resolved_output_dir = resolved_output_dir or (input_file.parent / "output")
        resolved_output_file = output_file or (resolved_output_dir / "normalized.xlsx")

        resolved_logs_dir = logs_dir
        if resolved_logs_dir and multiple_inputs:
            resolved_logs_dir = resolved_logs_dir / input_file.stem

        resolved_logs_file = logs_file
        if resolved_logs_file is None and resolved_logs_dir is not None:
            resolved_logs_file = resolved_logs_dir / default_logs_filename(log_format)

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


def parse_metadata(pairs: list[str]) -> dict[str, str]:
    meta: dict[str, str] = {}

    for raw in pairs:
        item = raw.strip()
        if not item:
            continue
        if "=" not in item:
            raise typer.BadParameter("--meta must be in KEY=VALUE form.", param_hint="--meta")

        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter("--meta must have a non-empty key before '='.", param_hint="--meta")

        meta[key] = value.strip()

    return meta


def print_text_summary(reports: list[RunReport], *, to_stderr: bool = False) -> None:
    typer.echo("Run summary:", err=to_stderr)
    for report in reports:
        if report.result is None:
            continue
        status = report.result.status.value if isinstance(report.result.status, RunStatus) else str(report.result.status)
        typer.echo(f"{status} | {report.plan.input_file} | output={report.plan.output_file}", err=to_stderr)


def _validate_log_format(log_format: str) -> str:
    value = (log_format or "text").strip().lower()
    if value not in _LOG_FORMATS:
        raise typer.BadParameter("--log-format must be 'text' or 'ndjson'.", param_hint="--log-format")
    return value


@app.command("run")
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
    include: list[str] = typer.Option([], "--include", help="Glob applied under --input-dir."),
    exclude: list[str] = typer.Option([], "--exclude", help="Glob to skip under --input-dir."),
    input_sheet: list[str] = typer.Option(
        [],
        "--input-sheet",
        "-s",
        help="Optional worksheet(s) to ingest; defaults to all visible sheets.",
    ),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True),
    output_file: Optional[Path] = typer.Option(None, "--output-file", file_okay=True, dir_okay=False),
    logs_dir: Optional[Path] = typer.Option(None, "--logs-dir", file_okay=False, dir_okay=True, help="(Optional) logs directory."),
    logs_file: Optional[Path] = typer.Option(None, "--logs-file", file_okay=True, dir_okay=False, help="(Optional) log output file path."),
    log_format: str = typer.Option("text", "--log-format", help="Log output format: text or ndjson."),
    meta: list[str] = typer.Option([], "--meta", help="Extra metadata KEY=VALUE included in all events (repeatable)."),
    config_package: Optional[str] = typer.Option(
        None,
        "--config-package",
        help=f"Config package to load (module name) or path to a config package directory (default: {Settings.config_package}).",
    ),
) -> None:
    """Execute the engine for one or more inputs."""

    log_format_value = _validate_log_format(log_format)

    if include and not input_dir:
        raise typer.BadParameter("--include requires --input-dir.")
    if exclude and not input_dir:
        raise typer.BadParameter("--exclude requires --input-dir.")

    settings = Settings()
    inputs = collect_input_files(input, input_dir, include, exclude, settings)
    if not inputs:
        raise typer.BadParameter("Provide --input and/or --input-dir (no inputs found).")

    plans = plan_runs(
        inputs,
        log_format=log_format_value,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir,
        logs_file=logs_file,
    )

    base_meta = parse_metadata(meta)
    engine = ADEngine(settings=settings)

    reports: list[RunReport] = []
    exit_code = 0

    for plan in plans:
        run_id = uuid4()
        request = RunRequest(
            run_id=run_id,
            config_package=config_package or settings.config_package,
            input_file=plan.input_file,
            input_sheets=list(input_sheet) if input_sheet else None,
            output_dir=plan.output_dir,
            output_file=plan.output_file,
            logs_dir=plan.logs_dir,
            logs_file=plan.logs_file,
            metadata=base_meta,
        )

        reporter = build_reporting(
            log_format_value,
            run_id=str(run_id),
            meta=base_meta,
            file_path=plan.logs_file,
        )

        # In NDJSON/stdout mode, keep stdout clean by redirecting stray prints to stderr.
        use_stdout = log_format_value == "ndjson" and plan.logs_file is None
        with protect_stdout(enabled=use_stdout):
            result = engine.run(request, logger=reporter.logger, event_emitter=reporter.emitter)

        reporter.close()

        reports.append(RunReport(plan=plan, result=result))
        if result.status != RunStatus.SUCCEEDED:
            exit_code = 1

    if log_format_value == "text":
        print_text_summary(reports, to_stderr=False)

    raise typer.Exit(code=exit_code)


@app.command("version")
def version_command(manifest_path: Optional[Path] = typer.Option(None, "--manifest-path")) -> None:
    """Print engine version and optionally validate/show manifest version."""

    import json

    from typer import BadParameter

    from ade_engine.schemas.manifest import ManifestV1

    payload: dict[str, str | None] = {"version": __version__}

    if manifest_path:
        path = Path(manifest_path)
        if path.suffix.lower() != ".toml":
            raise BadParameter("Manifest must be a TOML file", param_name="manifest_path")

        try:
            manifest_data = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BadParameter(f"Manifest file not found: {path}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise BadParameter(f"Invalid TOML in manifest: {exc}") from exc
        except OSError as exc:
            raise BadParameter(f"Unable to read manifest: {exc}") from exc

        manifest = ManifestV1.model_validate(manifest_data)
        payload["manifest_version"] = manifest.version

    typer.echo(json.dumps(payload))


def main() -> None:
    app()


__all__ = ["app", "main"]
