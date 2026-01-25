"""Worker loop orchestration."""

from __future__ import annotations

import logging
import random
import socket
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .db import assert_tables_exist, build_engine, build_sessionmaker
from .jobs.run import RunJob
from .gc import gc_environments, gc_run_artifacts
from .paths import PathManager
from .queue import EnvironmentQueue, RunQueue
from .repo import Repo
from .schema import REQUIRED_TABLES
from .settings import Settings, get_settings
from .subprocess_runner import SubprocessRunner
from .notifications import RunQueueListener, WakeSignal

logger = logging.getLogger("ade_worker")


def utcnow() -> datetime:
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


def _ensure_runtime_dirs(data_dir: Path, venvs_dir: Path) -> None:
    for sub in ["db", "workspaces", "cache/pip"]:
        _ensure_dir(data_dir / sub)
    _ensure_dir(venvs_dir)


def _next_gc_deadline(now_mono: float, interval_seconds: float) -> float:
    jitter = min(5.0, max(0.0, interval_seconds) * 0.05)
    return now_mono + max(0.0, interval_seconds) + (random.random() * jitter)


@dataclass(slots=True)
class WorkerLoop:
    settings: Settings
    SessionLocal: Any  # sqlalchemy.orm.sessionmaker
    worker_id: str
    run_queue: RunQueue
    run_job: RunJob
    paths: PathManager

    def _submit(
        self,
        *,
        executor: ThreadPoolExecutor,
        in_flight: set[Future[None]],
        wake_signal: WakeSignal,
        fn,
        claim,
    ) -> None:
        future = executor.submit(fn, claim)
        future.add_done_callback(lambda _f: wake_signal.work_done())
        in_flight.add(future)

    def _reap(self, *, in_flight: set[Future[None]]) -> None:
        done = {f for f in in_flight if f.done()}
        for f in done:
            in_flight.remove(f)
            try:
                f.result()
            except Exception:
                logger.exception("work item crashed")

    def _drain(
        self,
        *,
        executor: ThreadPoolExecutor,
        in_flight: set[Future[None]],
        wake_signal: WakeSignal,
        now: datetime,
    ) -> int:
        claimed_total = 0
        capacity = max(0, int(self.settings.worker_concurrency) - len(in_flight))
        if capacity <= 0:
            return 0

        while capacity > 0:
            batch_size = min(5, capacity)
            run_claims = self.run_queue.claim_batch(
                worker_id=self.worker_id,
                now=now,
                lease_seconds=int(self.settings.worker_lease_seconds),
                limit=batch_size,
            )
            if not run_claims:
                break
            for claim in run_claims:
                claimed_total += 1
                capacity -= 1
                self._submit(
                    executor=executor,
                    in_flight=in_flight,
                    wake_signal=wake_signal,
                    fn=self.run_job.process,
                    claim=claim,
                )

        return claimed_total

    def start(self) -> None:
        logger.info(
            "ade-worker starting worker_id=%s concurrency=%s",
            self.worker_id,
            self.settings.worker_concurrency,
        )

        cleanup_every = float(self.settings.worker_cleanup_interval)
        next_cleanup = time.monotonic() + cleanup_every

        gc_enabled = bool(self.settings.worker_enable_gc) and float(
            self.settings.worker_gc_interval_seconds
        ) > 0
        gc_interval = float(self.settings.worker_gc_interval_seconds)
        next_gc = _next_gc_deadline(time.monotonic(), gc_interval) if gc_enabled else None

        wake_signal = WakeSignal()
        listener = RunQueueListener(settings=self.settings, wake_signal=wake_signal)
        listener.start()

        with ThreadPoolExecutor(max_workers=int(self.settings.worker_concurrency)) as executor:
            in_flight: set[Future[None]] = set()
            try:
                startup_now = utcnow()
                startup_claimed = self._drain(
                    executor=executor,
                    in_flight=in_flight,
                    wake_signal=wake_signal,
                    now=startup_now,
                )
                if startup_claimed:
                    logger.info("run.queue.startup claimed=%s", startup_claimed)

                while True:
                    self._reap(in_flight=in_flight)

                    now = utcnow()
                    mono = time.monotonic()

                    if mono >= next_cleanup:
                        try:
                            expired_runs = int(self.run_queue.expire_stuck(now=now))
                            if expired_runs:
                                logger.info("expired %s stuck run leases", expired_runs)
                        except Exception:
                            logger.exception("run lease expiration failed")

                        next_cleanup = mono + cleanup_every

                    if next_gc is not None and mono >= next_gc:
                        try:
                            env_result = gc_environments(
                                SessionLocal=self.SessionLocal,
                                paths=self.paths,
                                now=now,
                                env_ttl_days=self.settings.worker_env_ttl_days,
                            )
                            if env_result.scanned:
                                logger.info(
                                    "gc environments scanned=%s deleted=%s skipped=%s failed=%s",
                                    env_result.scanned,
                                    env_result.deleted,
                                    env_result.skipped,
                                    env_result.failed,
                                )
                        except Exception:
                            logger.exception("environment GC failed")

                        if self.settings.worker_run_artifact_ttl_days is not None:
                            try:
                                run_result = gc_run_artifacts(
                                    SessionLocal=self.SessionLocal,
                                    paths=self.paths,
                                    now=now,
                                    run_ttl_days=self.settings.worker_run_artifact_ttl_days,
                                )
                                if run_result.scanned:
                                    logger.info(
                                        "gc run artifacts scanned=%s deleted=%s skipped=%s failed=%s",
                                        run_result.scanned,
                                        run_result.deleted,
                                        run_result.skipped,
                                        run_result.failed,
                                    )
                            except Exception:
                                logger.exception("run artifact GC failed")

                        next_gc = _next_gc_deadline(mono, gc_interval)

                    claimed = self._drain(
                        executor=executor,
                        in_flight=in_flight,
                        wake_signal=wake_signal,
                        now=now,
                    )
                    if claimed:
                        logger.info("run.queue.claimed count=%s", claimed)
                        continue
                    logger.debug("run.queue.claimed count=0")

                    listen_timeout = float(self.settings.worker_listen_timeout_seconds)
                    next_deadline = next_cleanup
                    if next_gc is not None:
                        next_deadline = min(next_deadline, next_gc)
                    wait_seconds = max(0.0, min(listen_timeout, next_deadline - mono))

                    notified = wake_signal.wait(wait_seconds)
                    if notified:
                        logger.info("run.queue.wake notify=true")
                        jitter_ms = int(self.settings.worker_notify_jitter_ms)
                        if jitter_ms > 0:
                            time.sleep(random.random() * (jitter_ms / 1000.0))
                    else:
                        logger.debug("run.queue.wake notify=false")
            finally:
                listener.stop()


def main() -> int:
    settings = get_settings()
    _setup_logging(settings.worker_log_level)

    _ensure_runtime_dirs(settings.data_dir, settings.venvs_dir)

    engine = build_engine(settings)

    assert_tables_exist(engine, REQUIRED_TABLES)

    worker_id = settings.worker_id or _default_worker_id()

    paths = PathManager(settings.data_dir, settings.venvs_dir)
    SessionLocal = build_sessionmaker(engine)

    repo = Repo(SessionLocal)

    env_queue = EnvironmentQueue(engine, SessionLocal)
    run_queue = RunQueue(
        engine,
        SessionLocal,
        backoff_base_seconds=int(settings.worker_backoff_base_seconds),
        backoff_max_seconds=int(settings.worker_backoff_max_seconds),
    )

    runner = SubprocessRunner()

    from .jobs.environment import EnvironmentJob

    env_job = EnvironmentJob(
        settings=settings,
        SessionLocal=SessionLocal,
        queue=env_queue,
        repo=repo,
        paths=paths,
        runner=runner,
        worker_id=worker_id,
    )
    run_job = RunJob(
        settings=settings,
        SessionLocal=SessionLocal,
        queue=run_queue,
        env_job=env_job,
        repo=repo,
        paths=paths,
        runner=runner,
        worker_id=worker_id,
    )

    WorkerLoop(
        settings=settings,
        SessionLocal=SessionLocal,
        worker_id=worker_id,
        run_queue=run_queue,
        run_job=run_job,
        paths=paths,
    ).start()
    return 0


__all__ = ["main", "WorkerLoop"]
