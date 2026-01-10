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

from .db import assert_tables_exist, create_db_engine
from .jobs.environment import EnvironmentJob
from .jobs.run import RunJob
from .gc import gc_environments, gc_run_artifacts
from .paths import PathManager
from .queue import EnvironmentQueue, RunQueue
from .repo import Repo
from .schema import REQUIRED_TABLES
from .settings import WorkerSettings
from .subprocess_runner import SubprocessRunner

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


def _ensure_runtime_dirs(data_dir: Path) -> None:
    for sub in ["db", "workspaces", "venvs", "cache/pip"]:
        _ensure_dir(data_dir / sub)


def _next_gc_deadline(now_mono: float, interval_seconds: float) -> float:
    jitter = min(5.0, max(0.0, interval_seconds) * 0.05)
    return now_mono + max(0.0, interval_seconds) + (random.random() * jitter)


@dataclass(slots=True)
class WorkerLoop:
    settings: WorkerSettings
    engine: Any  # sqlalchemy.Engine
    worker_id: str
    env_queue: EnvironmentQueue
    run_queue: RunQueue
    env_job: EnvironmentJob
    run_job: RunJob
    repo: Repo
    paths: PathManager

    def start(self) -> None:
        logger.info(
            "ade-worker starting worker_id=%s concurrency=%s",
            self.worker_id,
            self.settings.concurrency,
        )

        poll = float(self.settings.poll_interval)
        max_poll = float(self.settings.poll_interval_max)

        cleanup_every = float(self.settings.cleanup_interval)
        next_cleanup = time.monotonic() + cleanup_every

        gc_enabled = bool(self.settings.enable_gc) and float(self.settings.gc_interval_seconds) > 0
        gc_interval = float(self.settings.gc_interval_seconds)
        next_gc = _next_gc_deadline(time.monotonic(), gc_interval) if gc_enabled else None

        ensure_batch = max(10, int(self.settings.concurrency) * 5)

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
                        expired_runs = int(self.run_queue.expire_stuck(now=now))
                        if expired_runs:
                            logger.info("expired %s stuck run leases", expired_runs)
                    except Exception:
                        logger.exception("run lease expiration failed")

                    try:
                        expired_envs = int(self.env_queue.expire_stuck(now=now))
                        if expired_envs:
                            logger.info("expired %s stuck environment leases", expired_envs)
                    except Exception:
                        logger.exception("environment lease expiration failed")

                    next_cleanup = mono + cleanup_every

                if next_gc is not None and mono >= next_gc:
                    try:
                        env_result = gc_environments(
                            engine=self.engine,
                            paths=self.paths,
                            now=now,
                            env_ttl_days=self.settings.env_ttl_days,
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

                    if self.settings.run_artifact_ttl_days is not None:
                        try:
                            run_result = gc_run_artifacts(
                                engine=self.engine,
                                paths=self.paths,
                                now=now,
                                run_ttl_days=self.settings.run_artifact_ttl_days,
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

                # Ensure environments exist for queued runs (best effort).
                try:
                    self.repo.ensure_environment_rows_for_queued_runs(now=now, limit=ensure_batch)
                except Exception:
                    logger.exception("failed to ensure environment rows for queued runs")

                # Claim work while capacity remains.
                claimed_any = False
                while len(in_flight) < int(self.settings.concurrency):
                    env_claim = self.env_queue.claim_next(
                        worker_id=self.worker_id,
                        now=now,
                        lease_seconds=int(self.settings.lease_seconds),
                    )
                    if env_claim is not None:
                        claimed_any = True
                        in_flight.add(executor.submit(self.env_job.process, env_claim))
                        continue

                    run_claim = self.run_queue.claim_next(
                        worker_id=self.worker_id,
                        now=now,
                        lease_seconds=int(self.settings.lease_seconds),
                    )
                    if run_claim is None:
                        break
                    claimed_any = True
                    in_flight.add(executor.submit(self.run_job.process, run_claim))

                if claimed_any:
                    poll = float(self.settings.poll_interval)
                    continue

                # Idle backoff.
                time.sleep(poll)
                poll = min(max_poll, poll * 1.25 + 0.01)


def main() -> int:
    settings = WorkerSettings.load()
    _setup_logging(settings.log_level)

    _ensure_runtime_dirs(settings.data_dir)

    engine = create_db_engine(
        settings.database_url,
        sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        sqlite_journal_mode=settings.sqlite_journal_mode,
        sqlite_synchronous=settings.sqlite_synchronous,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )

    assert_tables_exist(engine, REQUIRED_TABLES)

    worker_id = settings.worker_id or _default_worker_id()

    paths = PathManager(settings.data_dir)
    repo = Repo(engine)

    env_queue = EnvironmentQueue(engine)
    run_queue = RunQueue(engine, backoff=settings.backoff_seconds)

    runner = SubprocessRunner()

    env_job = EnvironmentJob(
        settings=settings,
        engine=engine,
        queue=env_queue,
        repo=repo,
        paths=paths,
        runner=runner,
        worker_id=worker_id,
    )
    run_job = RunJob(
        settings=settings,
        engine=engine,
        queue=run_queue,
        repo=repo,
        paths=paths,
        runner=runner,
        worker_id=worker_id,
    )

    WorkerLoop(
        settings=settings,
        engine=engine,
        worker_id=worker_id,
        env_queue=env_queue,
        run_queue=run_queue,
        env_job=env_job,
        run_job=run_job,
        repo=repo,
        paths=paths,
    ).start()
    return 0


__all__ = ["main", "WorkerLoop"]
