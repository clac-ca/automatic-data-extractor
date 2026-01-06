"""Worker loop that executes queued builds and runs."""

from __future__ import annotations

import json
import logging
import os
import socket
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, Callable

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.engine import Engine

from .events import coerce_event_record, ensure_event_context, new_event_record
from .metrics import extract_run_columns, extract_run_fields, extract_run_metrics
from .schema import (
    builds,
    configurations,
    documents,
    document_changes,
    run_fields,
    run_metrics,
    run_table_columns,
    runs,
)
from .settings import WorkerSettings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunJob:
    row: dict[str, Any]


@dataclass(slots=True)
class BuildJob:
    row: dict[str, Any]


class Worker:
    """Process queued runs and builds using the database as the queue."""

    def __init__(self, *, engine: Engine, settings: WorkerSettings) -> None:
        self._engine = engine
        self._settings = settings
        self._stop = threading.Event()

    def start(self) -> None:
        threads: list[threading.Thread] = []
        for idx in range(self._settings.concurrency):
            t = threading.Thread(target=self._worker_loop, args=(idx,), daemon=True)
            threads.append(t)
            t.start()

        try:
            while any(t.is_alive() for t in threads):
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()
            for t in threads:
                t.join()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    def _worker_loop(self, idx: int) -> None:
        worker_id = self._settings.worker_id or f"{socket.gethostname()}:{os.getpid()}:{idx}"
        logger.info("worker.start", extra={"worker_id": worker_id})

        last_cleanup = 0.0
        last_metrics = 0.0
        sleep_seconds = self._settings.poll_interval
        max_sleep = max(self._settings.poll_interval_max, self._settings.poll_interval)
        while not self._stop.is_set():
            should_sleep = False
            try:
                now = time.monotonic()
                if now - last_cleanup >= self._settings.cleanup_interval:
                    self._expire_stuck_runs()
                    self._expire_stuck_builds()
                    self._fail_runs_with_failed_builds()
                    last_cleanup = now
                if now - last_metrics >= self._settings.metrics_interval:
                    self._log_queue_metrics()
                    last_metrics = now

                job = self._claim_next_job(worker_id)
                if job is None:
                    should_sleep = True
                elif isinstance(job, BuildJob):
                    sleep_seconds = self._settings.poll_interval
                    self._execute_build(job, worker_id=worker_id)
                else:
                    sleep_seconds = self._settings.poll_interval
                    self._execute_run(job, worker_id=worker_id)
            except Exception:
                logger.exception("worker.loop.error", extra={"worker_id": worker_id})
                should_sleep = True

            if should_sleep:
                time.sleep(sleep_seconds)
                sleep_seconds = min(max_sleep, sleep_seconds * 1.5)

        logger.info("worker.stop", extra={"worker_id": worker_id})

    # ------------------------------------------------------------------
    # Claiming
    # ------------------------------------------------------------------

    def _claim_next_job(self, worker_id: str) -> BuildJob | RunJob | None:
        build = self._claim_next_build(worker_id)
        if build is not None:
            return build
        run = self._claim_next_run(worker_id)
        if run is not None:
            return run
        return None

    def _claim_next_run(self, worker_id: str) -> RunJob | None:
        now = self._utc_now()
        lease_seconds = self._lease_seconds()
        lease_expires = now + timedelta(seconds=lease_seconds)

        if self._engine.dialect.name == "mssql":
            stmt = text(
                """
                UPDATE runs
                SET status = 'running',
                    claimed_by = :worker_id,
                    claim_expires_at = :lease_expires,
                    started_at = :now,
                    attempt_count = attempt_count + 1,
                    error_message = NULL
                OUTPUT inserted.*
                WHERE id = (
                    SELECT TOP (1) id
                    FROM runs WITH (UPDLOCK, READPAST, ROWLOCK)
                WHERE status = 'queued'
                  AND available_at <= :now
                  AND attempt_count < max_attempts
                  AND (
                    build_id IS NULL
                    OR EXISTS (
                        SELECT 1 FROM builds
                        WHERE builds.id = runs.build_id
                          AND builds.status = 'ready'
                    )
                  )
                ORDER BY available_at ASC, created_at ASC
            )
                """
            )
            with self._engine.begin() as conn:
                row = conn.execute(
                    stmt,
                    {
                        "worker_id": worker_id,
                        "lease_expires": lease_expires,
                        "now": now,
                    },
                ).mappings().first()
            if not row:
                return None
            job = RunJob(dict(row))
            self._log_job_claimed(job_type="run", row=job.row, now=now)
            return job

        supports_returning = bool(getattr(self._engine.dialect, "update_returning", False))
        with self._engine.begin() as conn:
            if supports_returning:
                candidate_subquery = (
                    select(runs.c.id)
                    .select_from(runs.outerjoin(builds, runs.c.build_id == builds.c.id))
                    .where(
                        and_(
                            runs.c.status == "queued",
                            runs.c.available_at <= now,
                            runs.c.attempt_count < runs.c.max_attempts,
                            or_(
                                runs.c.build_id.is_(None),
                                builds.c.status == "ready",
                            ),
                        )
                    )
                    .order_by(runs.c.available_at.asc(), runs.c.created_at.asc())
                    .limit(1)
                    .scalar_subquery()
                )
                stmt = (
                    update(runs)
                    .where(and_(runs.c.id == candidate_subquery, runs.c.status == "queued"))
                    .values(
                        status="running",
                        claimed_by=worker_id,
                        claim_expires_at=lease_expires,
                        started_at=now,
                        attempt_count=runs.c.attempt_count + 1,
                        error_message=None,
                    )
                    .returning(runs)
                )
                started = time.perf_counter()
                row = conn.execute(stmt).mappings().first()
                if logger.isEnabledFor(logging.DEBUG):
                    duration_ms = (time.perf_counter() - started) * 1000
                    logger.debug(
                        "worker.job.claim.query job_type=%s duration_ms=%.2f claimed=%s",
                        "run",
                        duration_ms,
                        bool(row),
                        extra={
                            "job_type": "run",
                            "duration_ms": round(duration_ms, 2),
                            "claimed": bool(row),
                        },
                    )
                if not row:
                    return None
                job = RunJob(dict(row))
                self._log_job_claimed(job_type="run", row=job.row, now=now)
                return job

            candidate = conn.execute(
                select(runs.c.id)
                .select_from(runs.outerjoin(builds, runs.c.build_id == builds.c.id))
                .where(
                    and_(
                        runs.c.status == "queued",
                        runs.c.available_at <= now,
                        runs.c.attempt_count < runs.c.max_attempts,
                        or_(
                            runs.c.build_id.is_(None),
                            builds.c.status == "ready",
                        ),
                    )
                )
                .order_by(runs.c.available_at.asc(), runs.c.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            if candidate is None:
                return None
            updated = conn.execute(
                update(runs)
                .where(and_(runs.c.id == candidate, runs.c.status == "queued"))
                .values(
                    status="running",
                    claimed_by=worker_id,
                    claim_expires_at=lease_expires,
                    started_at=now,
                    attempt_count=runs.c.attempt_count + 1,
                    error_message=None,
                )
            )
            if not updated.rowcount:
                return None
            row = conn.execute(select(runs).where(runs.c.id == candidate)).mappings().first()
            if not row:
                return None
            job = RunJob(dict(row))
            self._log_job_claimed(job_type="run", row=job.row, now=now)
            return job

    def _claim_next_build(self, worker_id: str) -> BuildJob | None:
        now = self._utc_now()

        if self._engine.dialect.name == "mssql":
            stmt = text(
                """
                UPDATE builds
                SET status = 'building',
                    started_at = :now
                OUTPUT inserted.*
                WHERE id = (
                    SELECT TOP (1) id
                    FROM builds WITH (UPDLOCK, READPAST, ROWLOCK)
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                )
                """
            )
            with self._engine.begin() as conn:
                row = conn.execute(stmt, {"now": now}).mappings().first()
            if not row:
                return None
            job = BuildJob(dict(row))
            self._log_job_claimed(job_type="build", row=job.row, now=now)
            return job

        supports_returning = bool(getattr(self._engine.dialect, "update_returning", False))
        with self._engine.begin() as conn:
            if supports_returning:
                candidate_subquery = (
                    select(builds.c.id)
                    .where(builds.c.status == "queued")
                    .order_by(builds.c.created_at.asc())
                    .limit(1)
                    .scalar_subquery()
                )
                stmt = (
                    update(builds)
                    .where(and_(builds.c.id == candidate_subquery, builds.c.status == "queued"))
                    .values(status="building", started_at=now)
                    .returning(builds)
                )
                started = time.perf_counter()
                row = conn.execute(stmt).mappings().first()
                if logger.isEnabledFor(logging.DEBUG):
                    duration_ms = (time.perf_counter() - started) * 1000
                    logger.debug(
                        "worker.job.claim.query job_type=%s duration_ms=%.2f claimed=%s",
                        "build",
                        duration_ms,
                        bool(row),
                        extra={
                            "job_type": "build",
                            "duration_ms": round(duration_ms, 2),
                            "claimed": bool(row),
                        },
                    )
                if not row:
                    return None
                job = BuildJob(dict(row))
                self._log_job_claimed(job_type="build", row=job.row, now=now)
                return job

            candidate = conn.execute(
                select(builds.c.id)
                .where(builds.c.status == "queued")
                .order_by(builds.c.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            if candidate is None:
                return None
            updated = conn.execute(
                update(builds)
                .where(and_(builds.c.id == candidate, builds.c.status == "queued"))
                .values(status="building", started_at=now)
            )
            if not updated.rowcount:
                return None
            row = conn.execute(select(builds).where(builds.c.id == candidate)).mappings().first()
            if not row:
                return None
            job = BuildJob(dict(row))
            self._log_job_claimed(job_type="build", row=job.row, now=now)
            return job

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_build(self, job: BuildJob, *, worker_id: str) -> None:
        build = job.row
        workspace_id = build["workspace_id"]
        configuration_id = build["configuration_id"]
        build_id = build["id"]

        log_path = self._build_logs_path(workspace_id, configuration_id, build_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Pre-create the log file so SSE tailing can attach immediately.
        log_path.touch(exist_ok=True)

        start_event = new_event_record(
            event="build.start",
            message="Build started",
            data={"status": "building"},
        )
        start_event = ensure_event_context(
            start_event,
            job_id=None,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )
        self._append_event(log_path, start_event)
        build_root = self._build_root(workspace_id, configuration_id, build_id)
        venv_root = build_root / ".venv"
        config_path = self._config_path(workspace_id, configuration_id)
        engine_spec = build.get("engine_spec") or self._settings.engine_spec
        engine_spec_value = str(engine_spec)
        candidate = Path(engine_spec_value)
        if candidate.exists():
            engine_spec_value = str(candidate.resolve())
        build_root.mkdir(parents=True, exist_ok=True)

        start_time = time.monotonic()

        def _remaining_timeout() -> int | None:
            timeout = self._settings.build_timeout_seconds
            if timeout is None:
                return None
            elapsed = time.monotonic() - start_time
            remaining = int(timeout - elapsed)
            return max(0, remaining)

        def _step(cmd: list[str], *, env: dict[str, str] | None = None) -> tuple[int, bool]:
            remaining = _remaining_timeout()
            if remaining is not None and remaining <= 0:
                return 1, True
            return self._run_subprocess(
                cmd,
                log_path,
                scope="build",
                timeout_seconds=remaining,
                context={
                    "workspace_id": workspace_id,
                    "configuration_id": configuration_id,
                    "build_id": build_id,
                },
                env=env,
            )

        try:
            if not config_path.exists():
                raise RuntimeError(f"Config package not found at {config_path}")
            if venv_root.exists():
                shutil.rmtree(venv_root, ignore_errors=True)

            # 1) Create virtual environment
            return_code, timed_out = _step(
                [sys.executable, "-m", "venv", str(venv_root)],
            )
            if timed_out:
                raise TimeoutError("Build timed out while creating venv")
            if return_code != 0:
                raise RuntimeError(f"venv creation failed with exit code {return_code}")

            venv_python = self._venv_python_path(venv_root)

            # 2) Upgrade pip/setuptools/wheel
            return_code, timed_out = _step(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "wheel",
                    "setuptools",
                ],
                env=self._pip_env(),
            )
            if timed_out:
                raise TimeoutError("Build timed out while upgrading pip")
            if return_code != 0:
                raise RuntimeError(f"pip upgrade failed with exit code {return_code}")

            # 3) Install engine
            return_code, timed_out = _step(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    engine_spec_value,
                ],
                env=self._pip_env(),
            )
            if timed_out:
                raise TimeoutError("Build timed out while installing engine")
            if return_code != 0:
                raise RuntimeError(f"engine install failed with exit code {return_code}")

            # 4) Install config package
            return_code, timed_out = _step(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "-e",
                    str(config_path),
                ],
                env=self._pip_env(),
            )
            if timed_out:
                raise TimeoutError("Build timed out while installing config package")
            if return_code != 0:
                raise RuntimeError(f"config install failed with exit code {return_code}")

            # 5) Verify imports
            return_code, timed_out = _step(
                [
                    str(venv_python),
                    "-c",
                    "import ade_engine, ade_config; print('ok')",
                ]
            )
            if timed_out:
                raise TimeoutError("Build timed out while verifying imports")
            if return_code != 0:
                raise RuntimeError(f"import verification failed with exit code {return_code}")

            python_version = self._probe_python_version(venv_python)
            engine_version = self._probe_engine_version(venv_python)

            finished_at = self._utc_now()
            summary = "Build succeeded"
            with self._engine.begin() as conn:
                conn.execute(
                    update(builds)
                    .where(builds.c.id == build_id)
                    .values(
                        status="ready",
                        finished_at=finished_at,
                        exit_code=0,
                        summary=summary,
                        error_message=None,
                        python_version=python_version,
                        python_interpreter=str(venv_python),
                        engine_version=engine_version,
                    )
                )
                conn.execute(
                    update(configurations)
                    .where(configurations.c.id == configuration_id)
                    .values(
                        active_build_id=build_id,
                        active_build_fingerprint=build.get("fingerprint"),
                    )
                )

            done_event = new_event_record(
                event="build.complete",
                message=summary,
                data={"status": "ready", "exit_code": 0},
            )
            done_event = ensure_event_context(
                done_event,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                build_id=build_id,
            )
            self._append_event(log_path, done_event)
            return
        except Exception as exc:
            self._cleanup_failed_build(venv_root)
            self._fail_build(
                build_id=build_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                log_path=log_path,
                error_message=str(exc),
                exit_code=1,
            )
            return

    def _execute_run(self, job: RunJob, *, worker_id: str) -> None:
        run = job.row
        run_id = run["id"]
        workspace_id = run["workspace_id"]
        configuration_id = run["configuration_id"]

        run_dir = self._run_dir(workspace_id, run_id)
        input_dir = run_dir / "input"
        output_dir = run_dir / "output"
        logs_dir = run_dir / "logs"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        event_log_path = logs_dir / "events.ndjson"
        # Pre-create the log file so SSE tailing can attach immediately.
        event_log_path.touch(exist_ok=True)

        start_event = new_event_record(
            event="run.start",
            message="Run started",
            data={"status": "in_progress", "mode": "execute"},
        )
        start_event = ensure_event_context(
            start_event,
            job_id=run_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=run.get("build_id"),
        )
        self._append_event(event_log_path, start_event)

        document_id = run.get("input_document_id")
        try:
            document = self._load_document(run)

            options = run.get("run_options") or {}
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except json.JSONDecodeError:
                    options = {}
            log_level = options.get("log_level") or "INFO"
            input_sheet_names = options.get("input_sheet_names") or run.get("input_sheet_names") or []
            if isinstance(input_sheet_names, str):
                try:
                    input_sheet_names = json.loads(input_sheet_names)
                except json.JSONDecodeError:
                    input_sheet_names = []
            active_sheet_only = bool(options.get("active_sheet_only"))
            validate_only = bool(options.get("validate_only"))
            dry_run = bool(options.get("dry_run"))

            if dry_run:
                self._complete_run(
                    run_id=run_id,
                    document_id=document["id"],
                    workspace_id=workspace_id,
                    status="succeeded",
                    exit_code=0,
                    error_message="Dry run requested",
                    event_log_path=event_log_path,
                    update_document=False,
                )
                return

            build_id = run.get("build_id")
            if not build_id:
                self._fail_run(
                    run_id=run_id,
                    document_id=document["id"],
                    workspace_id=workspace_id,
                    event_log_path=event_log_path,
                    error_message="Build is required before running",
                    exit_code=2,
                )
                return

            venv_root = self._build_root(workspace_id, configuration_id, str(build_id)) / ".venv"
            venv_python = self._venv_python_path(venv_root)
            if not venv_python.exists():
                self._fail_run(
                    run_id=run_id,
                    document_id=document["id"],
                    workspace_id=workspace_id,
                    event_log_path=event_log_path,
                    error_message="Build environment missing; rerun build",
                    exit_code=2,
                )
                self._fail_build(
                    build_id=str(build_id),
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    log_path=self._build_logs_path(workspace_id, configuration_id, str(build_id)),
                    error_message="Build environment missing; rerun build",
                    exit_code=2,
                )
                return

            if validate_only:
                cmd = [
                    str(venv_python),
                    "-m",
                    "ade_engine",
                    "config",
                    "validate",
                    "--config-package",
                    str(self._config_path(workspace_id, configuration_id)),
                    "--log-format",
                    "ndjson",
                ]
                return_code, timed_out = self._run_subprocess(
                    cmd,
                    event_log_path,
                    scope="run.validate",
                    context={
                        "job_id": run_id,
                        "workspace_id": workspace_id,
                        "configuration_id": configuration_id,
                        "build_id": str(build_id),
                    },
                    timeout_seconds=self._settings.build_timeout_seconds,
                )
                if timed_out:
                    self._fail_run(
                        run_id=run_id,
                        document_id=document["id"],
                        workspace_id=workspace_id,
                        event_log_path=event_log_path,
                        error_message=(
                            f"Validation timed out after {self._settings.build_timeout_seconds}s"
                        ),
                        exit_code=124,
                        update_document=False,
                    )
                    return
                status = "succeeded" if return_code == 0 else "failed"
                error_message = None if return_code == 0 else f"Validation exited with {return_code}"
                self._complete_run(
                    run_id=run_id,
                    document_id=document["id"],
                    workspace_id=workspace_id,
                    status=status,
                    exit_code=return_code,
                    error_message=error_message,
                    event_log_path=event_log_path,
                    update_document=False,
                )
                return

            staged_input = input_dir / document["original_filename"]
            source_path = self._document_path(workspace_id, document["stored_uri"])
            if staged_input.exists():
                staged_input.unlink()
            try:
                os.link(source_path, staged_input)
            except OSError:
                shutil.copy2(source_path, staged_input)

            now = self._utc_now()
            with self._engine.begin() as conn:
                conn.execute(
                    update(documents)
                    .where(documents.c.id == document["id"])
                    .values(
                        status="processing",
                        last_run_at=now,
                        updated_at=now,
                        version=documents.c.version + 1,
                    )
                )
                next_version = conn.execute(
                    select(documents.c.version)
                    .where(documents.c.id == document["id"])
                ).scalar_one()
                self._record_document_change(
                    conn,
                    workspace_id=workspace_id,
                    document_id=document["id"],
                    document_version=next_version,
                    occurred_at=now,
                )

            cmd = [str(venv_python), "-m", "ade_engine", "process", "file"]
            cmd.extend(["--input", str(staged_input)])
            cmd.extend(["--output-dir", str(output_dir)])
            cmd.extend(["--config-package", str(self._config_path(workspace_id, configuration_id))])
            cmd.extend(["--log-format", "ndjson", "--log-level", str(log_level)])
            if active_sheet_only:
                cmd.append("--active-sheet-only")
            else:
                for sheet in input_sheet_names:
                    cmd.extend(["--input-sheet", str(sheet)])

            lease_seconds = self._lease_seconds()
            heartbeat_interval = max(5.0, min(30.0, lease_seconds / 2))
            return_code, timed_out = self._run_subprocess(
                cmd,
                event_log_path,
                scope="run",
                context={
                    "job_id": run_id,
                    "workspace_id": workspace_id,
                    "configuration_id": configuration_id,
                    "build_id": str(build_id),
                },
                timeout_seconds=self._settings.run_timeout_seconds,
                heartbeat=lambda: self._extend_run_lease(run_id, worker_id),
                heartbeat_interval=heartbeat_interval,
            )

            if timed_out:
                self._fail_run(
                    run_id=run_id,
                    document_id=document["id"],
                    workspace_id=workspace_id,
                    event_log_path=event_log_path,
                    error_message=f"Run timed out after {self._settings.run_timeout_seconds}s",
                    exit_code=124,
                )
                return

            status = "succeeded" if return_code == 0 else "failed"
            error_message = None if return_code == 0 else f"Process exited with {return_code}"
            self._complete_run(
                run_id=run_id,
                document_id=document["id"],
                workspace_id=workspace_id,
                status=status,
                exit_code=return_code,
                error_message=error_message,
                event_log_path=event_log_path,
            )
        except Exception as exc:
            self._fail_run(
                run_id=run_id,
                document_id=document_id,
                workspace_id=workspace_id,
                event_log_path=event_log_path,
                error_message=str(exc),
                exit_code=1,
            )
            raise

    # ------------------------------------------------------------------
    # Subprocess + events
    # ------------------------------------------------------------------

    def _run_subprocess(
        self,
        cmd: list[str],
        event_log_path: Path,
        *,
        scope: str,
        context: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
        heartbeat: Callable[[], None] | None = None,
        heartbeat_interval: float = 30.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, bool]:
        logger.info("worker.subprocess.start", extra={"cmd": " ".join(cmd)})
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
            env=env,
        )

        queue: Queue[tuple[str, str]] = Queue()

        def _drain(stream, name: str) -> None:
            for line in iter(stream.readline, ""):
                queue.put((name, line.rstrip("\n")))
            stream.close()

        threads = [
            threading.Thread(target=_drain, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=_drain, args=(process.stderr, "stderr"), daemon=True),
        ]
        for t in threads:
            t.start()

        context = context or {}
        start_time = time.monotonic()
        next_heartbeat = start_time + heartbeat_interval
        timed_out = False
        while True:
            try:
                stream, line = queue.get(timeout=0.1)
            except Exception:
                if process.poll() is not None:
                    break
                stream, line = None, None

            now = time.monotonic()
            if timeout_seconds and now - start_time >= timeout_seconds:
                timed_out = True
                self._terminate_process(process)
                break
            if heartbeat and now >= next_heartbeat:
                try:
                    heartbeat()
                except Exception:
                    logger.exception("worker.heartbeat.error")
                next_heartbeat = now + heartbeat_interval

            if stream is None or line is None:
                continue
            if not line:
                continue

            parsed = coerce_event_record(line)
            if parsed:
                parsed = ensure_event_context(
                    parsed,
                    job_id=context.get("job_id"),
                    workspace_id=context.get("workspace_id"),
                    configuration_id=context.get("configuration_id"),
                    build_id=context.get("build_id"),
                )
                self._append_event(event_log_path, parsed)
                if parsed.get("event") == "engine.run.completed":
                    self._persist_run_completed(context.get("job_id"), parsed)
                continue

            level = "error" if stream == "stderr" else "info"
            event = new_event_record(
                event="console.line",
                message=line,
                level=level,
                data={"scope": scope, "stream": stream},
            )
            self._append_event(event_log_path, event)

        for t in threads:
            t.join(timeout=1)

        return process.wait(), timed_out

    def _append_event(self, path: Path, event: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False))
            handle.write("\n")

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _log_job_claimed(self, *, job_type: str, row: dict[str, Any], now: datetime) -> None:
        available_at = row.get("available_at") or row.get("created_at")
        latency_ms = None
        if isinstance(available_at, datetime):
            if available_at.tzinfo is None and now.tzinfo is not None:
                available_at = available_at.replace(tzinfo=now.tzinfo)
            latency_ms = max(0, int((now - available_at).total_seconds() * 1000))
        logger.info(
            "worker.job.claimed",
            extra={
                "job_type": job_type,
                "job_id": row.get("id"),
                "workspace_id": row.get("workspace_id"),
                "pickup_latency_ms": latency_ms,
            },
        )

    def _log_queue_metrics(self) -> None:
        now = self._utc_now()
        with self._engine.begin() as conn:
            queued_builds = conn.execute(
                select(func.count()).select_from(builds).where(builds.c.status == "queued")
            ).scalar_one()
            queued_runs = conn.execute(
                select(func.count()).select_from(runs).where(runs.c.status == "queued")
            ).scalar_one()
            ready_runs = conn.execute(
                select(func.count())
                .select_from(runs.outerjoin(builds, runs.c.build_id == builds.c.id))
                .where(
                    and_(
                        runs.c.status == "queued",
                        runs.c.available_at <= now,
                        runs.c.attempt_count < runs.c.max_attempts,
                        or_(runs.c.build_id.is_(None), builds.c.status == "ready"),
                    )
                )
            ).scalar_one()
        logger.info(
            "worker.queue.metrics",
            extra={
                "queued_builds": int(queued_builds or 0),
                "queued_runs": int(queued_runs or 0),
                "ready_runs": int(ready_runs or 0),
            },
        )

    def _load_document(self, run: dict[str, Any]) -> dict[str, Any]:
        doc_id = run["input_document_id"]
        with self._engine.begin() as conn:
            row = conn.execute(
                select(documents)
                .where(documents.c.id == doc_id)
                .limit(1)
            ).mappings().first()
        if row is None:
            raise RuntimeError(f"Document not found: {doc_id}")
        return dict(row)

    def _record_document_change(
        self,
        conn,
        *,
        workspace_id: str,
        document_id: str,
        document_version: int | None = None,
        client_request_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        conn.execute(
            document_changes.insert().values(
                workspace_id=workspace_id,
                document_id=document_id,
                type="upsert",
                document_version=document_version,
                client_request_id=client_request_id,
                payload={},
                occurred_at=occurred_at or self._utc_now(),
            )
        )

    def _complete_run(
        self,
        *,
        run_id: str,
        document_id: str,
        workspace_id: str | None = None,
        status: str,
        exit_code: int | None,
        error_message: str | None,
        event_log_path: Path,
        update_document: bool = True,
    ) -> None:
        now = self._utc_now()
        with self._engine.begin() as conn:
            conn.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(
                    status=status,
                    completed_at=now,
                    exit_code=exit_code,
                    error_message=error_message,
                    claimed_by=None,
                    claim_expires_at=None,
                )
            )
            if update_document and document_id:
                conn.execute(
                    update(documents)
                    .where(documents.c.id == document_id)
                    .values(
                        status="processed" if status == "succeeded" else "failed",
                        last_run_at=now,
                        updated_at=now,
                        version=documents.c.version + 1,
                    )
                )
                if workspace_id:
                    next_version = conn.execute(
                        select(documents.c.version)
                        .where(documents.c.id == document_id)
                    ).scalar_one()
                    self._record_document_change(
                        conn,
                        workspace_id=workspace_id,
                        document_id=document_id,
                        document_version=next_version,
                        occurred_at=now,
                    )
        level = "error" if status == "failed" else "info"
        done_event = new_event_record(
            event="run.complete",
            message=error_message or "Run completed",
            level=level,
            data={"status": status, "exit_code": exit_code},
        )
        done_event = ensure_event_context(
            done_event,
            job_id=run_id,
        )
        self._append_event(event_log_path, done_event)

    def _persist_run_completed(self, run_id: str | None, event: dict[str, Any]) -> None:
        if run_id is None:
            return
        payload = event.get("data")
        if not isinstance(payload, dict):
            return

        metrics = extract_run_metrics(payload)
        fields = extract_run_fields(payload.get("fields") or [])
        columns = extract_run_columns(payload.get("workbooks") or [])
        output_path = self._extract_output_path(run_id, payload)

        with self._engine.begin() as conn:
            if output_path:
                conn.execute(
                    update(runs)
                    .where(runs.c.id == run_id)
                    .values(output_path=output_path)
                )
            # Upsert run_metrics
            existing = conn.execute(
                select(run_metrics.c.run_id).where(run_metrics.c.run_id == run_id)
            ).first()
            if existing is None:
                conn.execute(run_metrics.insert().values(run_id=run_id, **metrics))
            else:
                conn.execute(
                    run_metrics.update()
                    .where(run_metrics.c.run_id == run_id)
                    .values(**metrics)
                )

            if fields:
                exists = conn.execute(
                    select(run_fields.c.run_id)
                    .where(run_fields.c.run_id == run_id)
                    .limit(1)
                ).first()
                if exists is None:
                    conn.execute(
                        run_fields.insert(),
                        [{"run_id": run_id, **row} for row in fields],
                    )

            if columns:
                exists = conn.execute(
                    select(run_table_columns.c.run_id)
                    .where(run_table_columns.c.run_id == run_id)
                    .limit(1)
                ).first()
                if exists is None:
                    conn.execute(
                        run_table_columns.insert(),
                        [{"run_id": run_id, **row} for row in columns],
                    )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _expire_stuck_runs(self) -> None:
        now = self._utc_now()
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(runs)
                .where(
                    and_(
                        runs.c.status == "running",
                        runs.c.claim_expires_at.is_not(None),
                        runs.c.claim_expires_at < now,
                    )
                )
            ).mappings().all()

            for run in rows:
                attempt_count = run.get("attempt_count") or 0
                max_attempts = run.get("max_attempts") or self._settings.job_max_attempts
                if attempt_count >= max_attempts:
                    conn.execute(
                        update(runs)
                        .where(runs.c.id == run["id"])
                        .values(
                            status="failed",
                            completed_at=now,
                            exit_code=1,
                            error_message="Run lease expired",
                            claimed_by=None,
                            claim_expires_at=None,
                        )
                    )
                    continue

                delay = self._retry_delay_seconds(attempt_count)
                conn.execute(
                    update(runs)
                    .where(runs.c.id == run["id"])
                    .values(
                        status="queued",
                        available_at=now + timedelta(seconds=delay),
                        claimed_by=None,
                        claim_expires_at=None,
                        started_at=None,
                        completed_at=None,
                        exit_code=None,
                        error_message="Run lease expired",
                    )
                )

    def _expire_stuck_builds(self) -> None:
        horizon = self._utc_now() - timedelta(seconds=self._settings.build_timeout_seconds)
        with self._engine.begin() as conn:
            conn.execute(
                update(builds)
                .where(and_(builds.c.status == "building", builds.c.started_at < horizon))
                .values(
                    status="failed",
                    finished_at=self._utc_now(),
                    exit_code=1,
                    error_message=f"Build timed out after {self._settings.build_timeout_seconds}s",
                )
            )

    def _fail_runs_with_failed_builds(self) -> None:
        now = self._utc_now()
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(runs.c.id)
                .select_from(runs.join(builds, runs.c.build_id == builds.c.id))
                .where(
                    and_(
                        runs.c.status == "queued",
                        builds.c.status.in_(["failed", "cancelled"]),
                    )
                )
            ).all()
            for (run_id,) in rows:
                conn.execute(
                    update(runs)
                    .where(runs.c.id == run_id)
                    .values(
                        status="failed",
                        completed_at=now,
                        exit_code=1,
                        error_message="Build failed before run could start",
                        claimed_by=None,
                        claim_expires_at=None,
                    )
                )

    # ------------------------------------------------------------------
    # Paths + helpers
    # ------------------------------------------------------------------

    def _run_dir(self, workspace_id: str, run_id: str) -> Path:
        return self._settings.runs_dir / str(workspace_id) / "runs" / str(run_id)

    def _relative_run_path(
        self,
        *,
        workspace_id: str | None,
        run_id: str,
        path: str | None,
    ) -> str | None:
        if not workspace_id or not path:
            return None
        run_dir = self._run_dir(workspace_id, run_id).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (run_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        try:
            relative = candidate.relative_to(run_dir)
        except ValueError:
            return None
        if not candidate.exists():
            return None
        return str(relative)

    def _extract_output_path(self, run_id: str, payload: dict[str, Any]) -> str | None:
        outputs = payload.get("outputs")
        if not isinstance(outputs, dict):
            return None
        normalized = outputs.get("normalized")
        if not isinstance(normalized, dict):
            return None
        raw_path = normalized.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        workspace_id = payload.get("workspaceId")
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            workspace_id = None
        return self._relative_run_path(
            workspace_id=workspace_id,
            run_id=run_id,
            path=raw_path,
        )

    def _document_path(self, workspace_id: str, stored_uri: str) -> Path:
        root = self._settings.documents_dir / str(workspace_id) / "documents"
        return (root / stored_uri.lstrip("/")).resolve()

    def _config_path(self, workspace_id: str, configuration_id: str) -> Path:
        return (
            self._settings.configs_dir
            / str(workspace_id)
            / "config_packages"
            / str(configuration_id)
        )

    def _build_root(self, workspace_id: str, configuration_id: str, build_id: str) -> Path:
        return (
            self._settings.venvs_dir
            / str(workspace_id)
            / str(configuration_id)
            / str(build_id)
        )

    def _build_logs_path(self, workspace_id: str, configuration_id: str, build_id: str) -> Path:
        return self._build_root(workspace_id, configuration_id, build_id) / "logs" / "events.ndjson"

    def _venv_python_path(self, venv_root: Path) -> Path:
        if os.name == "nt":
            return venv_root / "Scripts" / "python.exe"
        return venv_root / "bin" / "python"

    def _pip_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        env.setdefault("PIP_NO_INPUT", "1")
        env.setdefault("PIP_PROGRESS_BAR", "off")
        env.setdefault("PIP_CACHE_DIR", str(self._settings.pip_cache_dir))
        return env

    def _probe_python_version(self, python_bin: Path) -> str | None:
        try:
            output = subprocess.check_output(
                [
                    str(python_bin),
                    "-c",
                    "import sys; print('.'.join(map(str, sys.version_info[:3])))",
                ],
                text=True,
            )
            return output.strip()
        except Exception:
            logger.warning("worker.python_version.detect_failed", exc_info=True)
            return None

    def _probe_engine_version(self, python_bin: Path) -> str | None:
        try:
            output = subprocess.check_output(
                [
                    str(python_bin),
                    "-c",
                    "import ade_engine; print(getattr(ade_engine, '__version__', ''))",
                ],
                text=True,
            )
            value = output.strip()
            return value or None
        except Exception:
            logger.warning("worker.engine_version.detect_failed", exc_info=True)
            return None

    def _cleanup_failed_build(self, venv_root: Path) -> None:
        if venv_root.exists():
            shutil.rmtree(venv_root, ignore_errors=True)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(tz=UTC)

    def _lease_seconds(self) -> int:
        lease = int(self._settings.job_lease_seconds)
        if self._settings.run_timeout_seconds:
            lease = max(lease, int(self._settings.run_timeout_seconds))
        return lease

    def _retry_delay_seconds(self, attempt_count: int) -> int:
        base = self._settings.job_backoff_base_seconds
        delay = base * (2 ** max(attempt_count - 1, 0))
        return min(self._settings.job_backoff_max_seconds, delay)

    def _extend_run_lease(self, run_id: str, worker_id: str) -> None:
        now = self._utc_now()
        lease_expires = now + timedelta(seconds=self._lease_seconds())
        with self._engine.begin() as conn:
            conn.execute(
                update(runs)
                .where(and_(runs.c.id == run_id, runs.c.claimed_by == worker_id))
                .values(claim_expires_at=lease_expires)
            )

    def _fail_run(
        self,
        *,
        run_id: str,
        document_id: str | None,
        workspace_id: str | None = None,
        event_log_path: Path,
        error_message: str,
        exit_code: int,
        update_document: bool = True,
    ) -> None:
        try:
            self._complete_run(
                run_id=run_id,
                document_id=document_id or "",
                workspace_id=workspace_id,
                status="failed",
                exit_code=exit_code,
                error_message=error_message,
                event_log_path=event_log_path,
                update_document=update_document,
            )
        except Exception:
            logger.exception("worker.run.fail.error", extra={"run_id": run_id})

    def _fail_build(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        log_path: Path,
        error_message: str,
        exit_code: int,
    ) -> None:
        finished_at = self._utc_now()
        with self._engine.begin() as conn:
            conn.execute(
                update(builds)
                .where(builds.c.id == build_id)
                .values(
                    status="failed",
                    finished_at=finished_at,
                    exit_code=exit_code,
                    error_message=error_message,
                )
            )
        done_event = new_event_record(
            event="build.complete",
            message=error_message,
            level="error",
            data={"status": "failed", "exit_code": exit_code},
        )
        done_event = ensure_event_context(
            done_event,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )
        self._append_event(log_path, done_event)

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if hasattr(os, "killpg"):
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except Exception:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except Exception:
                process.kill()
            process.wait(timeout=5)


__all__ = ["Worker"]
