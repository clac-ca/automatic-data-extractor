"""Run execution job."""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..paths import PathManager
from ..queue import RunClaim, RunQueue
from ..repo import Repo
from ..run_results import parse_run_fields, parse_run_metrics, parse_run_table_columns
from ..settings import WorkerSettings
from ..subprocess_runner import EventLog, SubprocessRunner

logger = logging.getLogger("ade_worker")


def utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=None)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path) -> None:
    _ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def _json_loads(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return value


def _json_loads_dict(value: Any) -> dict[str, Any]:
    obj = _json_loads(value)
    return obj if isinstance(obj, dict) else {}


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return False


def _as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        try:
            return int(v.strip())
        except ValueError:
            return None
    return None


def _as_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _as_str_list(v: Any) -> list[str]:
    if isinstance(v, list):
        out: list[str] = []
        for item in v:
            s = _as_str(item)
            if s:
                out.append(s)
        return out
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    return []


def _as_datetime(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _execution_payload(started_at: datetime, completed_at: datetime) -> dict[str, Any]:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    duration_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
    return {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": duration_ms,
    }


def _emit_run_complete(
    event_log: EventLog,
    *,
    status: str,
    message: str,
    context: dict[str, Any],
    started_at: datetime,
    completed_at: datetime,
    exit_code: int | None,
    error_message: str | None = None,
    output_path: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "execution": _execution_payload(started_at, completed_at),
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if error_message:
        payload["error_message"] = error_message
    if output_path:
        payload["output_path"] = output_path

    level = "error" if status == "failed" else "info"
    event_log.emit(event="run.complete", level=level, message=message, data=payload, context=context)


@dataclass(slots=True)
class RunOptions:
    validate_only: bool = False
    dry_run: bool = False
    log_level: str = "INFO"
    input_sheet_names: list[str] = None  # type: ignore[assignment]
    active_sheet_only: bool = False
    max_findings_per_sheet: int | None = None
    extra_engine_args: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_sheet_names = self.input_sheet_names or []
        self.extra_engine_args = self.extra_engine_args or []


def parse_run_options(raw: Any, *, default_log_level: str) -> RunOptions:
    opts = _json_loads_dict(raw)
    return RunOptions(
        validate_only=_as_bool(opts.get("validate_only") or opts.get("validation_only")),
        dry_run=_as_bool(opts.get("dry_run")),
        log_level=(_as_str(opts.get("log_level")) or default_log_level).upper(),
        input_sheet_names=_as_str_list(opts.get("input_sheet_names")),
        active_sheet_only=_as_bool(opts.get("active_sheet_only")),
        max_findings_per_sheet=_as_int(opts.get("max_findings_per_sheet")),
        extra_engine_args=_as_str_list(opts.get("engine_args") or opts.get("extra_args")),
    )


def _parse_input_sheet_names(value: Any) -> list[str]:
    payload = _json_loads(value)
    return _as_str_list(payload)


def engine_config_validate_cmd(*, python_bin: Path, config_dir: Path, log_level: str) -> list[str]:
    return [
        str(python_bin),
        "-m",
        "ade_engine",
        "config",
        "validate",
        "--config-package",
        str(config_dir),
        "--log-format",
        "ndjson",
        "--log-level",
        log_level.upper(),
    ]


def engine_process_file_cmd(
    *,
    python_bin: Path,
    input_path: Path,
    output_dir: Path,
    config_dir: Path,
    options: RunOptions,
    sheet_names: list[str],
) -> list[str]:
    cmd = [
        str(python_bin),
        "-m",
        "ade_engine",
        "process",
        "file",
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--config-package",
        str(config_dir),
        "--log-format",
        "ndjson",
        "--log-level",
        options.log_level.upper(),
    ]
    if options.max_findings_per_sheet is not None and options.max_findings_per_sheet >= 0:
        cmd.extend(["--max-findings-per-sheet", str(options.max_findings_per_sheet)])
    if options.active_sheet_only:
        cmd.append("--active-sheet-only")
    else:
        for sheet in sheet_names:
            s = str(sheet).strip()
            if s:
                cmd.extend(["--input-sheet", s])
    cmd.extend(options.extra_engine_args or [])
    return cmd


def _extract_output_path(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        return None
    normalized = outputs.get("normalized")
    if not isinstance(normalized, dict):
        return None
    path = normalized.get("path")
    return str(path) if isinstance(path, str) and path.strip() else None


@dataclass(slots=True)
class RunJob:
    settings: WorkerSettings
    engine: Any  # sqlalchemy.Engine
    queue: RunQueue
    repo: Repo
    paths: PathManager
    runner: SubprocessRunner
    worker_id: str

    def _pip_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        env["PIP_NO_INPUT"] = "1"
        env["PIP_PROGRESS_BAR"] = "off"
        env["PIP_CACHE_DIR"] = str(self.paths.pip_cache_dir())
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _heartbeat_run(self, run: RunClaim) -> None:
        self.queue.heartbeat(
            run_id=run.id,
            worker_id=self.worker_id,
            now=utcnow(),
            lease_seconds=int(self.settings.lease_seconds),
        )

    def _retry_at(self, run: RunClaim, now: datetime) -> datetime | None:
        if run.attempt_count < run.max_attempts:
            delay = self.settings.backoff_seconds(run.attempt_count)
            return now + timedelta(seconds=int(delay))
        return None

    def _release_for_env(self, run: RunClaim, *, now: datetime, error_message: str) -> None:
        retry_at = now + timedelta(seconds=5)
        with self.engine.begin() as conn:
            ok = self.queue.release_for_env(
                conn=conn,
                run_id=run.id,
                worker_id=self.worker_id,
                retry_at=retry_at,
                error_message=error_message,
            )
        if ok:
            logger.info("run.requeued.env_not_ready run_id=%s", run.id)

    def process(self, claim: RunClaim) -> None:
        now = utcnow()
        run_id = claim.id

        run = self.repo.load_run(run_id)
        if not run:
            logger.error("run not found: %s", run_id)
            return

        run_started_at = _as_datetime(run.get("started_at")) or now

        workspace_id = str(run["workspace_id"])
        configuration_id = str(run["configuration_id"])
        document_id = str(run["input_document_id"])

        env = self.repo.load_ready_environment_for_run(run)
        if not env:
            self._release_for_env(claim, now=now, error_message="Environment not ready")
            return

        environment_id = str(env["id"])
        deps_digest = str(env["deps_digest"])

        ctx = {
            "job_id": run_id,
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "environment_id": environment_id,
        }

        event_log = EventLog(self.paths.run_event_log_path(workspace_id, run_id))
        event_log.emit(event="run.start", message="Starting run", context=ctx)

        venv_dir = self.paths.environment_venv_dir(
            workspace_id,
            configuration_id,
            deps_digest,
            environment_id,
        )
        python_bin = self.paths.python_in_venv(venv_dir)
        if not python_bin.exists():
            logger.warning("environment python missing: %s", python_bin)
            with self.engine.begin() as conn:
                self.repo.mark_environment_queued(
                    conn=conn,
                    env_id=environment_id,
                    now=now,
                    error_message="Missing venv python; requeueing environment",
                )
            self._release_for_env(claim, now=now, error_message="Environment missing on disk")
            return

        config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
        if not config_dir.exists():
            self._handle_run_failure(
                claim,
                run_id,
                document_id,
                event_log,
                ctx,
                now,
                run_started_at,
                2,
                f"Missing config package dir: {config_dir}",
            )
            return

        with self.engine.begin() as conn:
            self.repo.touch_environment_last_used(conn=conn, env_id=environment_id, now=now)

        options = parse_run_options(run.get("run_options"), default_log_level=self.settings.log_level)
        sheet_names = options.input_sheet_names or _parse_input_sheet_names(run.get("input_sheet_names"))

        if options.dry_run:
            finished_at = utcnow()
            with self.engine.begin() as conn:
                ok = self.queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
                if not ok:
                    event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                    return
                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=finished_at,
                    exit_code=0,
                    output_path=None,
                    error_message="Dry run",
                )
            _emit_run_complete(
                event_log,
                status="succeeded",
                message="Dry run complete",
                context=ctx,
                started_at=run_started_at,
                completed_at=finished_at,
                exit_code=0,
            )
            return

        if options.validate_only:
            cmd = engine_config_validate_cmd(python_bin=python_bin, config_dir=config_dir, log_level=options.log_level)
            res = self.runner.run(
                cmd,
                event_log=event_log,
                scope="run.validate",
                timeout_seconds=float(self.settings.run_timeout_seconds) if self.settings.run_timeout_seconds else None,
                cwd=None,
                env=self._pip_env(),
                heartbeat=lambda: self._heartbeat_run(claim),
                heartbeat_interval=max(1.0, self.settings.lease_seconds / 3),
                context=ctx,
            )
            finished_at = utcnow()
            if res.exit_code == 0:
                with self.engine.begin() as conn:
                    ok = self.queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
                    if not ok:
                        event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                        return
                    self.repo.record_run_result(
                        conn=conn,
                        run_id=run_id,
                        completed_at=finished_at,
                        exit_code=0,
                        output_path=None,
                        error_message=None,
                    )
                _emit_run_complete(
                    event_log,
                    status="succeeded",
                    message="Validation succeeded",
                    context=ctx,
                    started_at=run_started_at,
                    completed_at=finished_at,
                    exit_code=0,
                )
            else:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    finished_at,
                    run_started_at,
                    res.exit_code,
                    f"Validation failed (exit {res.exit_code})",
                )
            return

        # Stage document input
        doc = self.repo.load_document(document_id)
        if not doc:
            self._handle_run_failure(
                claim,
                run_id,
                document_id,
                event_log,
                ctx,
                now,
                run_started_at,
                2,
                f"Document not found: {document_id}",
            )
            return

        source_path = self.paths.document_storage_path(workspace_id=workspace_id, stored_uri=str(doc.get("stored_uri") or ""))
        if not source_path.exists():
            self._handle_run_failure(
                claim,
                run_id,
                document_id,
                event_log,
                ctx,
                now,
                run_started_at,
                2,
                f"Document file missing: {source_path}",
            )
            return

        input_dir = self.paths.run_input_dir(workspace_id, run_id)
        output_dir = self.paths.run_output_dir(workspace_id, run_id)
        _ensure_dir(input_dir)
        _ensure_dir(output_dir)

        original_name = Path(str(doc.get("original_filename") or "input")).name
        staged_input = input_dir / original_name
        _copy_file(source_path, staged_input)

        # Mark document processing (best effort; not fatal if it fails).
        try:
            with self.engine.begin() as conn:
                self.repo.update_document_status(
                    conn=conn,
                    document_id=document_id,
                    status="processing",
                    now=utcnow(),
                )
        except Exception:
            logger.exception("failed to mark document processing")

        # Run engine
        engine_payload: dict[str, Any] | None = None

        def on_event(rec: dict[str, Any]) -> None:
            nonlocal engine_payload
            if rec.get("event") == "engine.run.completed":
                data = rec.get("data")
                if isinstance(data, dict):
                    engine_payload = data

        cmd = engine_process_file_cmd(
            python_bin=python_bin,
            input_path=staged_input,
            output_dir=output_dir,
            config_dir=config_dir,
            options=options,
            sheet_names=sheet_names,
        )

        res = self.runner.run(
            cmd,
            event_log=event_log,
            scope="run.engine",
            timeout_seconds=float(self.settings.run_timeout_seconds) if self.settings.run_timeout_seconds else None,
            cwd=None,
            env=self._pip_env(),
            heartbeat=lambda: self._heartbeat_run(claim),
            heartbeat_interval=max(1.0, self.settings.lease_seconds / 3),
            context=ctx,
            on_json_event=on_event,
        )

        finished_at = utcnow()

        if res.timed_out:
            self._handle_run_failure(
                claim,
                run_id,
                document_id,
                event_log,
                ctx,
                finished_at,
                run_started_at,
                res.exit_code,
                "Run timed out",
            )
            return

        if res.exit_code == 0:
            output_path = _extract_output_path(engine_payload)
            results_payload = engine_payload if isinstance(engine_payload, dict) else None
            metrics = parse_run_metrics(results_payload) if results_payload else None
            fields = parse_run_fields(results_payload) if results_payload else []
            columns = parse_run_table_columns(results_payload) if results_payload else []
            with self.engine.begin() as conn:
                ok = self.queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
                if not ok:
                    event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                    return

                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=finished_at,
                    exit_code=0,
                    output_path=output_path,
                    error_message=None,
                )
                self.repo.update_document_status(
                    conn=conn,
                    document_id=document_id,
                    status="processed",
                    now=finished_at,
                )

                if results_payload is None:
                    logger.warning("run.results.missing_payload run_id=%s", run_id)
                else:
                    try:
                        with conn.begin_nested():
                            self.repo.replace_run_metrics(conn=conn, run_id=run_id, metrics=metrics)
                            self.repo.replace_run_fields(conn=conn, run_id=run_id, rows=fields)
                            self.repo.replace_run_table_columns(conn=conn, run_id=run_id, rows=columns)
                    except Exception:
                        logger.exception("run.results.persist_failed run_id=%s", run_id)

            _emit_run_complete(
                event_log,
                status="succeeded",
                message="Run succeeded",
                context=ctx,
                started_at=run_started_at,
                completed_at=finished_at,
                exit_code=0,
                output_path=output_path,
            )
            return

        # Failure
        self._handle_run_failure(
            claim,
            run_id,
            document_id,
            event_log,
            ctx,
            finished_at,
            run_started_at,
            res.exit_code,
            f"Engine failed (exit {res.exit_code})",
        )

    def _handle_run_failure(
        self,
        claim: RunClaim,
        run_id: str,
        document_id: str,
        event_log: EventLog,
        ctx: dict[str, Any],
        now: datetime,
        started_at: datetime,
        exit_code: int,
        error_message: str,
    ) -> None:
        retry_at = self._retry_at(claim, now)

        with self.engine.begin() as conn:
            ok = self.queue.ack_failure(
                conn=conn,
                run_id=run_id,
                worker_id=self.worker_id,
                now=now,
                error_message=error_message,
                retry_at=retry_at,
            )
            if not ok:
                event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                return

            if retry_at is None:
                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=now,
                    exit_code=exit_code,
                    output_path=None,
                    error_message=error_message,
                )
                self.repo.update_document_status(
                    conn=conn,
                    document_id=document_id,
                    status="failed",
                    now=now,
                )
            else:
                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=None,
                    exit_code=None,
                    output_path=None,
                    error_message=error_message,
                )

        if retry_at is not None:
            event_log.emit(
                event="run.retry",
                level="error",
                message=f"Retry scheduled at {retry_at.isoformat()}",
                data={
                    "error_message": error_message,
                    "retry_at": retry_at.isoformat(),
                    "exit_code": exit_code,
                },
                context=ctx,
            )
            return

        _emit_run_complete(
            event_log,
            status="failed",
            message=error_message,
            context=ctx,
            started_at=started_at,
            completed_at=now,
            exit_code=exit_code,
            error_message=error_message,
        )


__all__ = ["RunJob", "RunOptions", "parse_run_options"]
