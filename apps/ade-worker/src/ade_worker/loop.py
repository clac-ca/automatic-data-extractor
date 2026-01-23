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
from .jobs.environment import EnvironmentJob
from .jobs.run import RunJob
from .gc import gc_environments, gc_run_artifacts
from .paths import PathManager
from .queue import EnvironmentQueue, RunQueue
from .repo import Repo
from .schema import REQUIRED_TABLES
from .settings import Settings, get_settings
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
            self.settings.worker_concurrency,
        )

        poll = float(self.settings.worker_poll_interval)
        max_poll = float(self.settings.worker_poll_interval_max)

        cleanup_every = float(self.settings.worker_cleanup_interval)
        next_cleanup = time.monotonic() + cleanup_every

        gc_enabled = bool(self.settings.worker_enable_gc) and float(
            self.settings.worker_gc_interval_seconds
        ) > 0
        gc_interval = float(self.settings.worker_gc_interval_seconds)
        next_gc = _next_gc_deadline(time.monotonic(), gc_interval) if gc_enabled else None

        ensure_batch = max(10, int(self.settings.worker_concurrency) * 5)
        ensure_interval = max(1.0, float(self.settings.worker_poll_interval_max))
        next_ensure = time.monotonic()

        with ThreadPoolExecutor(max_workers=int(self.settings.worker_concurrency)) as executor:
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

                # Ensure environments exist for queued runs (best effort).
                if mono >= next_ensure:
                    try:
                        if self.repo.has_queued_runs(now=now):
                            self.repo.ensure_environment_rows_for_queued_runs(
                                now=now,
                                limit=ensure_batch,
                            )
                    except Exception:
                        logger.exception("failed to ensure environment rows for queued runs")
                    next_ensure = mono + ensure_interval

                # Claim work while capacity remains.
                claimed_any = False
                while len(in_flight) < int(self.settings.worker_concurrency):
                    env_claim = self.env_queue.claim_next(
                        worker_id=self.worker_id,
                        now=now,
                        lease_seconds=int(self.settings.worker_lease_seconds),
                    )
                    if env_claim is not None:
                        claimed_any = True
                        in_flight.add(executor.submit(self.env_job.process, env_claim))
                        continue

                    run_claim = self.run_queue.claim_next(
                        worker_id=self.worker_id,
                        now=now,
                        lease_seconds=int(self.settings.worker_lease_seconds),
                    )
                    if run_claim is None:
                        break
                    claimed_any = True
                    in_flight.add(executor.submit(self.run_job.process, run_claim))

                if claimed_any:
                    poll = float(self.settings.worker_poll_interval)
                    continue

                # Idle backoff.
                time.sleep(poll)
                poll = min(max_poll, poll * 1.25 + 0.01 + (random.random() * 0.05))


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
    run_queue = RunQueue(engine, SessionLocal, backoff=settings.backoff_seconds)

    runner = SubprocessRunner()

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
        repo=repo,
        paths=paths,
        runner=runner,
        worker_id=worker_id,
    )

    WorkerLoop(
        settings=settings,
        SessionLocal=SessionLocal,
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
