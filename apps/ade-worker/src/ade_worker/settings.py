"""ade-worker settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    return float(raw)


def _env_path(name: str, default: Path) -> Path:
    raw = _env(name)
    if raw is None:
        return default
    return Path(raw).expanduser().resolve()


def _env_log_level(*names: str, default: str = "INFO") -> str:
    for name in names:
        raw = _env(name)
        if raw is not None:
            return raw.strip().upper()
    return default


@dataclass(slots=True)
class WorkerSettings:
    """Environment-driven configuration for the worker."""

    # Shared ADE settings (ADE_*)
    database_url: str
    database_sqlite_journal_mode: str
    database_sqlite_synchronous: str
    database_sqlite_busy_timeout_ms: int
    workspaces_dir: Path
    documents_dir: Path
    configs_dir: Path
    runs_dir: Path
    venvs_dir: Path
    pip_cache_dir: Path
    engine_spec: str
    build_timeout_seconds: int
    run_timeout_seconds: int | None

    # Worker-specific (ADE_WORKER_*)
    concurrency: int
    poll_interval: float
    poll_interval_max: float
    cleanup_interval: float
    metrics_interval: float
    worker_id: str | None
    job_lease_seconds: int
    job_max_attempts: int
    job_backoff_base_seconds: int
    job_backoff_max_seconds: int
    log_level: str

    @classmethod
    def load(cls) -> "WorkerSettings":
        workspaces_dir = _env_path("ADE_WORKSPACES_DIR", Path("./data/workspaces"))
        documents_dir = _env_path("ADE_DOCUMENTS_DIR", workspaces_dir)
        configs_dir = _env_path("ADE_CONFIGS_DIR", workspaces_dir)
        runs_dir = _env_path("ADE_RUNS_DIR", workspaces_dir)
        venvs_dir = _env_path("ADE_VENVS_DIR", Path("./data/venvs"))

        run_timeout = _env("ADE_RUN_TIMEOUT_SECONDS")
        run_timeout_seconds = int(run_timeout) if run_timeout else None

        cpu_count = os.cpu_count() or 2
        default_concurrency = max(1, min(4, cpu_count // 2))

        return cls(
            database_url=_env("ADE_DATABASE_URL", "sqlite:///./data/db/ade.sqlite"),
            database_sqlite_journal_mode=(_env("ADE_DATABASE_SQLITE_JOURNAL_MODE", "WAL") or "WAL").upper(),
            database_sqlite_synchronous=(_env("ADE_DATABASE_SQLITE_SYNCHRONOUS", "NORMAL") or "NORMAL").upper(),
            database_sqlite_busy_timeout_ms=_env_int("ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS", 30000),
            workspaces_dir=workspaces_dir,
            documents_dir=documents_dir,
            configs_dir=configs_dir,
            runs_dir=runs_dir,
            venvs_dir=venvs_dir,
            pip_cache_dir=_env_path("ADE_PIP_CACHE_DIR", Path("./data/cache/pip")),
            engine_spec=_env("ADE_ENGINE_SPEC", "apps/ade-engine"),
            build_timeout_seconds=_env_int("ADE_BUILD_TIMEOUT", 600),
            run_timeout_seconds=run_timeout_seconds,
            concurrency=_env_int("ADE_WORKER_CONCURRENCY", default_concurrency),
            poll_interval=_env_float("ADE_WORKER_POLL_INTERVAL", 0.5),
            poll_interval_max=_env_float("ADE_WORKER_POLL_INTERVAL_MAX", 2.0),
            cleanup_interval=_env_float("ADE_WORKER_CLEANUP_INTERVAL", 30.0),
            metrics_interval=_env_float("ADE_WORKER_METRICS_INTERVAL", 30.0),
            worker_id=_env("ADE_WORKER_ID"),
            job_lease_seconds=_env_int("ADE_WORKER_JOB_LEASE_SECONDS", 900),
            job_max_attempts=_env_int("ADE_WORKER_JOB_MAX_ATTEMPTS", 3),
            job_backoff_base_seconds=_env_int("ADE_WORKER_JOB_BACKOFF_BASE_SECONDS", 5),
            job_backoff_max_seconds=_env_int("ADE_WORKER_JOB_BACKOFF_MAX_SECONDS", 300),
            log_level=_env_log_level("ADE_WORKER_LOG_LEVEL", "ADE_LOG_LEVEL", default="INFO"),
        )


__all__ = ["WorkerSettings"]
