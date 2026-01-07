"""Worker process: claim builds/runs from the DB and execute them.

This is deliberately a single-process design with a thread pool for concurrency.
No brokers, no Redis.

Contracts:
- The main application inserts rows into `builds`/`runs` with queued status.
- The worker claims builds/runs, executes them, and updates status on completion.
- Build work prepares an isolated venv for a configuration.
- Run work stages an input document and executes `ade_engine` in the build venv.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update

from .db import create_db_engine, maybe_create_schema
from .paths import PathManager
from .queue import BuildClaim, BuildQueue, RunClaim, RunQueue
from .schema import REQUIRED_TABLES, builds, documents, metadata, runs
from .settings import WorkerSettings
from .subprocess_runner import EventLog, SubprocessRunner


logger = logging.getLogger("ade_worker")


def utcnow() -> datetime:
    # Store naive UTC in the database (portable across SQLite + SQL Server).
    return datetime.utcnow().replace(tzinfo=None)


def _default_worker_id() -> str:
    host = socket.gethostname() or "worker"
    return f"{host}-{uuid4().hex[:8]}"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
    )


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _hardlink_or_copy(src: Path, dst: Path) -> None:
    _ensure_dir(dst.parent)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _json_loads_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _run_capture_text(cmd: list[str]) -> str:
    """Run a short command and return combined stdout+stderr."""
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    return out or err




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
    return []


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


class Repo:
    def __init__(self, engine) -> None:
        self.engine = engine

    def load_build(self, build_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(builds).where(builds.c.id == build_id)).mappings().first()
        return dict(row) if row else None

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        return dict(row) if row else None

    def load_document(self, document_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(documents).where(documents.c.id == document_id)).mappings().first()
        return dict(row) if row else None

    def update_document_status(self, *, document_id: str, status: str, now: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(documents)
                .where(documents.c.id == document_id)
                .values(status=status, updated_at=now)
            )

    def record_build_result(
        self,
        *,
        conn,
        build_id: str,
        finished_at: datetime | None,
        python_interpreter: str | None,
        python_version: str | None,
        engine_version: str | None,
        summary: str | None,
        error_message: str | None,
        status: str,
        exit_code: int | None,
        expected_status: str | None = None,
    ) -> bool:
        stmt = update(builds).where(builds.c.id == build_id)
        if expected_status:
            stmt = stmt.where(builds.c.status == expected_status)
        result = conn.execute(
            stmt.values(
                status=status,
                exit_code=exit_code,
                finished_at=finished_at,
                python_interpreter=python_interpreter,
                python_version=python_version,
                engine_version=engine_version,
                summary=summary,
                error_message=error_message,
            )
        )
        return bool(getattr(result, "rowcount", 0) == 1)

    def record_run_result(
        self,
        *,
        conn,
        run_id: str,
        completed_at: datetime | None,
        exit_code: int | None,
        output_path: str | None,
        error_message: str | None,
    ) -> None:
        conn.execute(
            update(runs)
            .where(runs.c.id == run_id)
            .values(
                completed_at=completed_at,
                exit_code=exit_code,
                output_path=output_path,
                error_message=error_message,
            )
        )


@dataclass(slots=True)
class JobProcessor:
    settings: WorkerSettings
    engine: Any  # sqlalchemy.Engine
    run_queue: RunQueue
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
        self.run_queue.heartbeat(
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

    # ---- Build ----

    def _process_build(self, claim: BuildClaim) -> None:
        build_id = claim.id

        build = self.repo.load_build(build_id)
        if not build:
            logger.error("build not found: %s", build_id)
            return

        workspace_id = str(build["workspace_id"])
        configuration_id = str(build["configuration_id"])

        build_root = self.paths.build_root(workspace_id, configuration_id, build_id)
        venv_dir = self.paths.venv_dir(workspace_id, configuration_id, build_id)
        event_log = EventLog(self.paths.build_event_log_path(workspace_id, configuration_id, build_id))
        ctx = {"job_id": build_id, "workspace_id": workspace_id, "configuration_id": configuration_id}

        # Clean slate per attempt (prevents weird partial state).
        if build_root.exists():
            shutil.rmtree(build_root, ignore_errors=True)
        _ensure_dir(build_root)

        event_log.emit(event="build.start", message="Starting build", context=ctx)

        deadline = time.monotonic() + float(self.settings.build_timeout_seconds)
        pip_env = self._pip_env()
        last_exit_code: int | None = None

        def remaining() -> float:
            return max(0.1, deadline - time.monotonic())

        try:
            # 1) venv
            create_cmd = [sys.executable, "-m", "venv", str(venv_dir)]
            res = self.runner.run(
                create_cmd,
                event_log=event_log,
                scope="build.venv",
                timeout_seconds=remaining(),
                cwd=None,
                env=pip_env,
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"venv creation failed (exit {res.exit_code})")

            python_bin = self.paths.python_in_venv(venv_dir)
            if not python_bin.exists():
                raise RuntimeError(f"venv python missing: {python_bin}")

            # 2) install engine
            engine_spec = (build.get("engine_spec") or self.settings.engine_spec)
            install_engine = [str(python_bin), "-m", "pip", "install"]
            if Path(str(engine_spec)).exists():
                install_engine.extend(["-e", str(engine_spec)])
            else:
                install_engine.append(str(engine_spec))

            res = self.runner.run(
                install_engine,
                event_log=event_log,
                scope="build.engine",
                timeout_seconds=remaining(),
                cwd=None,
                env=pip_env,
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"engine install failed (exit {res.exit_code})")

            # 3) install config package (editable)
            config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
            if not config_dir.exists():
                raise RuntimeError(f"config package dir missing: {config_dir}")

            res = self.runner.run(
                [str(python_bin), "-m", "pip", "install", "-e", str(config_dir)],
                event_log=event_log,
                scope="build.config",
                timeout_seconds=remaining(),
                cwd=None,
                env=pip_env,
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"config install failed (exit {res.exit_code})")

            # 4) probe versions
            python_version = _run_capture_text([str(python_bin), "--version"])
            try:
                engine_version = subprocess.check_output(
                    [str(python_bin), "-c", "import ade_engine; print(getattr(ade_engine, '__version__', 'unknown'))"],
                    text=True,
                ).strip()
            except Exception:
                engine_version = None

            event_log.emit(event="build.versions", message=f"python={python_version} engine={engine_version or 'unknown'}", context=ctx)

            finished_at = utcnow()

            with self.engine.begin() as conn:
                ok = self.repo.record_build_result(
                    conn=conn,
                    build_id=build_id,
                    finished_at=finished_at,
                    python_interpreter=str(python_bin),
                    python_version=python_version,
                    engine_version=engine_version,
                    summary="Build completed",
                    error_message=None,
                    status="ready",
                    exit_code=0,
                    expected_status="building",
                )

            if not ok:
                event_log.emit(event="build.lost_claim", level="warning", message="Build status changed before completion", context=ctx)
                return

            event_log.emit(event="build.complete", message="Build succeeded", context=ctx)

        except Exception as exc:
            err = str(exc)
            logger.exception("build failed: %s", err)

            finished_at = utcnow()
            exit_code = last_exit_code or 1

            with self.engine.begin() as conn:
                ok = self.repo.record_build_result(
                    conn=conn,
                    build_id=build_id,
                    finished_at=finished_at,
                    python_interpreter=None,
                    python_version=None,
                    engine_version=None,
                    summary=None,
                    error_message=err,
                    status="failed",
                    exit_code=exit_code,
                    expected_status="building",
                )

            if not ok:
                event_log.emit(event="build.lost_claim", level="warning", message="Build status changed before failure ack", context=ctx)
                return

            event_log.emit(event="build.failed", level="error", message=err, context=ctx)

    # ---- Run ----

    def _process_run(self, claim: RunClaim) -> None:
        now = utcnow()
        run_id = claim.id

        run = self.repo.load_run(run_id)
        if not run:
            logger.error("run not found: %s", run_id)
            return

        workspace_id = str(run["workspace_id"])
        configuration_id = str(run["configuration_id"])
        build_id = str(run["build_id"])
        document_id = str(run["input_document_id"])

        ctx = {"job_id": run_id, "workspace_id": workspace_id, "configuration_id": configuration_id, "build_id": build_id}

        event_log = EventLog(self.paths.run_event_log_path(workspace_id, run_id))
        event_log.emit(event="run.start", message="Starting run", context=ctx)

        # Build must exist and its venv python must exist.
        build = self.repo.load_build(build_id)
        if not build:
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, now, 2, f"Build not found: {build_id}")
            return

        venv_dir = self.paths.venv_dir(workspace_id, configuration_id, build_id)
        python_bin = self.paths.python_in_venv(venv_dir)
        if not python_bin.exists():
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, now, 2, f"Missing build venv python: {python_bin}")
            return

        config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
        if not config_dir.exists():
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, now, 2, f"Missing config package dir: {config_dir}")
            return

        options = parse_run_options(run.get("run_options"), default_log_level=self.settings.log_level)
        sheet_names = options.input_sheet_names or []

        if options.dry_run:
            finished_at = utcnow()
            with self.engine.begin() as conn:
                ok = self.run_queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
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
            event_log.emit(event="run.complete", message="Dry run complete", context=ctx)
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
                    ok = self.run_queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
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
                event_log.emit(event="run.complete", message="Validation succeeded", context=ctx)
            else:
                self._handle_run_failure(claim, run_id, document_id, event_log, ctx, finished_at, res.exit_code, f"Validation failed (exit {res.exit_code})")
            return

        # Stage document input
        doc = self.repo.load_document(document_id)
        if not doc:
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, now, 2, f"Document not found: {document_id}")
            return

        source_path = self.paths.document_storage_path(workspace_id=workspace_id, stored_uri=str(doc.get("stored_uri") or ""))
        if not source_path.exists():
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, now, 2, f"Document file missing: {source_path}")
            return

        input_dir = self.paths.run_input_dir(workspace_id, run_id)
        output_dir = self.paths.run_output_dir(workspace_id, run_id)
        _ensure_dir(input_dir)
        _ensure_dir(output_dir)

        original_name = Path(str(doc.get("original_filename") or "input")).name
        staged_input = input_dir / original_name
        _hardlink_or_copy(source_path, staged_input)

        # Mark document processing (best effort; not fatal if it fails).
        try:
            self.repo.update_document_status(document_id=document_id, status="processing", now=utcnow())
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
            scope="run",
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
            self._handle_run_failure(claim, run_id, document_id, event_log, ctx, finished_at, res.exit_code, "Run timed out")
            return

        if res.exit_code == 0:
            # Success
            output_path = _extract_output_path(engine_payload)
            with self.engine.begin() as conn:
                ok = self.run_queue.ack_success(conn=conn, run_id=run_id, worker_id=self.worker_id, now=finished_at)
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
                conn.execute(
                    update(documents)
                    .where(documents.c.id == document_id)
                    .values(status="processed", updated_at=finished_at)
                )

            event_log.emit(event="run.complete", message="Run succeeded", context=ctx)
            return

        # Failure
        self._handle_run_failure(claim, run_id, document_id, event_log, ctx, finished_at, res.exit_code, f"Engine failed (exit {res.exit_code})")

    def _handle_run_failure(
        self,
        claim: RunClaim,
        run_id: str,
        document_id: str,
        event_log: EventLog,
        ctx: dict[str, Any],
        now: datetime,
        exit_code: int,
        error_message: str,
    ) -> None:
        retry_at = self._retry_at(claim, now)

        with self.engine.begin() as conn:
            ok = self.run_queue.ack_failure(
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
                # Terminal failure: record result + mark document failed.
                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=now,
                    exit_code=exit_code,
                    output_path=None,
                    error_message=error_message,
                )
                conn.execute(
                    update(documents)
                    .where(documents.c.id == document_id)
                    .values(status="failed", updated_at=now)
                )
            else:
                # Retry: keep the last error visible on the run row (optional).
                self.repo.record_run_result(
                    conn=conn,
                    run_id=run_id,
                    completed_at=None,
                    exit_code=None,
                    output_path=None,
                    error_message=error_message,
                )

        if retry_at is not None:
            event_log.emit(event="run.retry", level="error", message=f"Retry scheduled at {retry_at.isoformat()}", context=ctx)
        else:
            event_log.emit(event="run.failed", level="error", message=error_message, context=ctx)


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
class Worker:
    engine: Any  # sqlalchemy.Engine
    settings: WorkerSettings
    worker_id: str
    build_queue: BuildQueue
    run_queue: RunQueue
    processor: JobProcessor

    def start(self) -> None:
        logger.info("ade-worker starting worker_id=%s concurrency=%s", self.worker_id, self.settings.concurrency)

        poll = float(self.settings.poll_interval)
        max_poll = float(self.settings.poll_interval_max)

        cleanup_every = float(self.settings.cleanup_interval)
        next_cleanup = time.monotonic() + cleanup_every

        with ThreadPoolExecutor(max_workers=int(self.settings.concurrency)) as executor:
            in_flight: set[Future[None]] = set()

            while True:
                # Reap completed work items.
                done = {f for f in in_flight if f.done()}
                for f in done:
                    in_flight.remove(f)
                    try:
                        f.result()
                    except Exception:
                        logger.exception("work item crashed")

                now = utcnow()

                # Periodic cleanup: expire stuck leases.
                mono = time.monotonic()
                if mono >= next_cleanup:
                    try:
                        expired = int(self.run_queue.expire_stuck(now=now))
                        if expired:
                            logger.info("expired %s stuck run leases", expired)
                    except Exception:
                        logger.exception("lease expiration failed")
                    next_cleanup = mono + cleanup_every

                # Claim work while capacity remains.
                claimed_any = False
                while len(in_flight) < int(self.settings.concurrency):
                    build_claim = self.build_queue.claim_next(now=now)
                    if build_claim is not None:
                        claimed_any = True
                        in_flight.add(executor.submit(self.processor._process_build, build_claim))
                        continue

                    run_claim = self.run_queue.claim_next(
                        worker_id=self.worker_id,
                        now=now,
                        lease_seconds=int(self.settings.lease_seconds),
                    )
                    if run_claim is None:
                        break
                    claimed_any = True
                    in_flight.add(executor.submit(self.processor._process_run, run_claim))

                if claimed_any:
                    poll = float(self.settings.poll_interval)
                    continue

                # Idle backoff.
                time.sleep(poll)
                poll = min(max_poll, poll * 1.25 + 0.01)


def _ensure_runtime_dirs(data_dir: Path) -> None:
    for sub in ["db", "workspaces", "venvs", "cache/pip"]:
        _ensure_dir(data_dir / sub)


def main() -> int:
    settings = WorkerSettings.load()
    _setup_logging(settings.log_level)

    _ensure_runtime_dirs(settings.data_dir)

    engine = create_db_engine(
        settings.database_url,
        sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        sqlite_journal_mode=settings.sqlite_journal_mode,
        sqlite_synchronous=settings.sqlite_synchronous,
    )

    maybe_create_schema(engine, auto_create=settings.auto_create_schema, required_tables=REQUIRED_TABLES, metadata=metadata)

    worker_id = settings.worker_id or _default_worker_id()

    paths = PathManager(settings.data_dir)
    repo = Repo(engine)

    build_queue = BuildQueue(engine)
    run_queue = RunQueue(engine, backoff=settings.backoff_seconds)

    processor = JobProcessor(
        settings=settings,
        engine=engine,
        run_queue=run_queue,
        repo=repo,
        paths=paths,
        runner=SubprocessRunner(),
        worker_id=worker_id,
    )

    Worker(
        engine=engine,
        settings=settings,
        worker_id=worker_id,
        build_queue=build_queue,
        run_queue=run_queue,
        processor=processor,
    ).start()
    return 0


__all__ = ["main", "Worker"]
