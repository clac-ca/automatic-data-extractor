"""ADE Worker settings (Pydantic v2, clean-slate)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from settings import (
    BlobStorageSettingsMixin,
    DatabaseSettingsMixin,
    DataPathsSettingsMixin,
    ade_settings_config,
    create_settings_accessors,
    normalize_log_format,
    normalize_log_level,
)


class Settings(
    DataPathsSettingsMixin,
    BlobStorageSettingsMixin,
    DatabaseSettingsMixin,
    BaseSettings,
):
    """Worker settings loaded from ADE_* env vars (and repo-root .env)."""

    model_config = ade_settings_config(populate_by_name=True)

    # ---- Worker identity & loop -------------------------------------------
    worker_id: str | None = None
    worker_run_concurrency: int = Field(2, ge=1)
    worker_listen_timeout_seconds: float = Field(60.0, gt=0)
    worker_cleanup_interval: float = Field(30.0, gt=0)
    log_format: str = "console"
    log_level: str | None = None
    worker_log_level: str | None = None

    # ---- Garbage collection (run via scheduled job) -----------------------
    worker_cache_ttl_days: int = Field(30, ge=0)
    worker_run_artifact_ttl_days: int | None = Field(30, ge=0)

    # ---- Queue leasing / retries ------------------------------------------
    worker_lease_seconds: int = Field(900, ge=1)
    worker_backoff_base_seconds: int = Field(5, ge=0)
    worker_backoff_max_seconds: int = Field(300, ge=0)

    # ---- Runtime filesystem ------------------------------------------------
    worker_cache_dir: Path = Field(default=Path("/tmp/ade-worker-cache"))

    # ---- Timeouts ----------------------------------------------------------
    worker_env_build_timeout_seconds: int = Field(600, ge=1)
    worker_run_timeout_seconds: int | None = None

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        self.log_format = normalize_log_format(self.log_format, env_var="ADE_LOG_FORMAT")
        self.log_level = normalize_log_level(self.log_level, env_var="ADE_LOG_LEVEL")
        self.worker_log_level = normalize_log_level(
            self.worker_log_level,
            env_var="ADE_WORKER_LOG_LEVEL",
        )
        return self

    @property
    def effective_worker_log_level(self) -> str:
        return self.worker_log_level or self.log_level or "INFO"

    @property
    def runs_dir(self) -> Path:
        return self.worker_runs_dir

    @property
    def worker_runs_dir(self) -> Path:
        return self.worker_cache_dir / "runs"

    @property
    def worker_venvs_dir(self) -> Path:
        return self.worker_cache_dir / "venvs"

    @property
    def worker_uv_cache_dir(self) -> Path:
        return self.worker_cache_dir / "uv"

    def backoff_seconds(self, attempt_count: int) -> int:
        base = max(0, int(self.worker_backoff_base_seconds))
        delay = base * (2 ** max(attempt_count - 1, 0))
        return min(int(self.worker_backoff_max_seconds), int(delay))


get_settings, reload_settings = create_settings_accessors(Settings)


__all__ = ["Settings", "get_settings", "reload_settings"]
