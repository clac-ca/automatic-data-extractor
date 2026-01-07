"""Worker settings loaded from environment variables.

Keep this intentionally boring and explicit: no hidden defaults, no magic config files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip()
    return raw if raw else default


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    raw = raw.lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _env_path(name: str, default: Path) -> Path:
    raw = _env(name)
    if raw is None:
        return default
    return Path(raw).expanduser().resolve()


def _default_concurrency() -> int:
    cpu = os.cpu_count() or 2
    # Conservative default: avoid thrashing local dev machines.
    return max(1, min(4, cpu // 2))


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    # Database
    database_url: str
    sqlite_busy_timeout_ms: int
    sqlite_journal_mode: str
    sqlite_synchronous: str
    auto_create_schema: bool

    # Worker identity & loop
    worker_id: str | None
    concurrency: int
    poll_interval: float
    poll_interval_max: float
    cleanup_interval: float
    log_level: str

    # Queue leasing / retries
    lease_seconds: int
    backoff_base_seconds: int
    backoff_max_seconds: int
    max_attempts_default: int

    # Runtime filesystem
    data_dir: Path
    engine_spec: str

    # Timeouts
    build_timeout_seconds: int
    run_timeout_seconds: int | None

    @classmethod
    def load(cls) -> "WorkerSettings":
        data_dir = _env_path("ADE_WORKER_DATA_DIR", Path("./data"))

        run_timeout_raw = _env("ADE_WORKER_RUN_TIMEOUT_SECONDS")
        run_timeout_seconds = int(run_timeout_raw) if run_timeout_raw else None

        return cls(
            database_url=_env("ADE_DATABASE_URL", "sqlite:///./data/db/ade.sqlite") or "sqlite:///./data/db/ade.sqlite",
            sqlite_busy_timeout_ms=_env_int("ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS", 30000),
            sqlite_journal_mode=(_env("ADE_DATABASE_SQLITE_JOURNAL_MODE", "WAL") or "WAL").upper(),
            sqlite_synchronous=(_env("ADE_DATABASE_SQLITE_SYNCHRONOUS", "NORMAL") or "NORMAL").upper(),
            auto_create_schema=_env_bool("ADE_WORKER_AUTO_CREATE_SCHEMA", default=False),

            worker_id=_env("ADE_WORKER_ID"),
            concurrency=_env_int("ADE_WORKER_CONCURRENCY", _default_concurrency()),
            poll_interval=_env_float("ADE_WORKER_POLL_INTERVAL", 0.5),
            poll_interval_max=_env_float("ADE_WORKER_POLL_INTERVAL_MAX", 2.0),
            cleanup_interval=_env_float("ADE_WORKER_CLEANUP_INTERVAL", 30.0),
            log_level=(_env("ADE_WORKER_LOG_LEVEL", "INFO") or "INFO").upper(),

            lease_seconds=_env_int("ADE_WORKER_LEASE_SECONDS", 900),
            backoff_base_seconds=_env_int("ADE_WORKER_BACKOFF_BASE_SECONDS", 5),
            backoff_max_seconds=_env_int("ADE_WORKER_BACKOFF_MAX_SECONDS", 300),
            max_attempts_default=_env_int("ADE_WORKER_MAX_ATTEMPTS_DEFAULT", 3),

            data_dir=data_dir,
            engine_spec=_env("ADE_WORKER_ENGINE_SPEC", "apps/ade-engine") or "apps/ade-engine",

            build_timeout_seconds=_env_int("ADE_WORKER_BUILD_TIMEOUT_SECONDS", 600),
            run_timeout_seconds=run_timeout_seconds,
        )

    def backoff_seconds(self, attempt_count: int) -> int:
        """Exponential backoff in seconds.

        attempt_count is 1-based (first attempt == 1).
        """
        base = max(0, int(self.backoff_base_seconds))
        delay = base * (2 ** max(attempt_count - 1, 0))
        return min(int(self.backoff_max_seconds), int(delay))
