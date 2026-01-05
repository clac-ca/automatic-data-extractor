from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ade_worker.settings import WorkerSettings
from ade_worker.worker import Worker


def _make_settings(tmp_path: Path) -> WorkerSettings:
    return WorkerSettings(
        database_url="sqlite:///:memory:",
        database_sqlite_journal_mode="WAL",
        database_sqlite_synchronous="NORMAL",
        database_sqlite_busy_timeout_ms=30000,
        workspaces_dir=tmp_path / "workspaces",
        documents_dir=tmp_path / "workspaces",
        configs_dir=tmp_path / "workspaces",
        runs_dir=tmp_path / "workspaces",
        venvs_dir=tmp_path / "venvs",
        engine_spec="ade_engine",
        build_timeout_seconds=2,
        run_timeout_seconds=2,
        concurrency=1,
        poll_interval=0.1,
        cleanup_interval=1.0,
        worker_id="test-worker",
        job_lease_seconds=30,
        job_max_attempts=3,
        job_backoff_base_seconds=1,
        job_backoff_max_seconds=10,
        log_level="INFO",
    )


def test_run_subprocess_heartbeat_called(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    settings = _make_settings(tmp_path)
    worker = Worker(engine=engine, settings=settings)

    log_path = tmp_path / "events.ndjson"
    heartbeat_calls: list[float] = []

    def heartbeat() -> None:
        heartbeat_calls.append(time.monotonic())

    cmd = [sys.executable, "-c", "import time; time.sleep(0.35)"]
    return_code, timed_out = worker._run_subprocess(
        cmd,
        log_path,
        scope="test",
        timeout_seconds=1,
        heartbeat=heartbeat,
        heartbeat_interval=0.05,
    )

    assert timed_out is False
    assert return_code == 0
    assert len(heartbeat_calls) >= 1


def test_run_subprocess_timeout(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    settings = _make_settings(tmp_path)
    worker = Worker(engine=engine, settings=settings)

    log_path = tmp_path / "events.ndjson"
    cmd = [sys.executable, "-c", "import time; time.sleep(1.0)"]
    return_code, timed_out = worker._run_subprocess(
        cmd,
        log_path,
        scope="test",
        timeout_seconds=0.3,
        heartbeat_interval=0.05,
    )

    assert timed_out is True
    assert return_code != 0
