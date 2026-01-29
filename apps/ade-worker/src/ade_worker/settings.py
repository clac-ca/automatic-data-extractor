"""ADE Worker settings (Pydantic v2, clean-slate)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker settings loaded from ADE_* env vars (and repo-root .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    # ---- Database (match ade-api field names) ------------------------------
    database_url: PostgresDsn = Field(..., description="Postgres database URL.")
    database_echo: bool = False

    database_auth_mode: Literal["password", "managed_identity"] = Field(
        default="password"
    )
    database_sslrootcert: str | None = Field(default=None)

    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)

    # ---- Worker identity & loop -------------------------------------------
    worker_id: str | None = None
    worker_concurrency: int = Field(2, ge=1)
    worker_listen_timeout_seconds: float = Field(60.0, gt=0)
    worker_cleanup_interval: float = Field(30.0, gt=0)
    worker_log_level: str = "INFO"

    # ---- Garbage collection (run via scheduled job) -----------------------
    worker_env_ttl_days: int = Field(30, ge=0)
    worker_run_artifact_ttl_days: int | None = Field(30, ge=0)

    # ---- Queue leasing / retries ------------------------------------------
    worker_lease_seconds: int = Field(900, ge=1)
    worker_backoff_base_seconds: int = Field(5, ge=0)
    worker_backoff_max_seconds: int = Field(300, ge=0)
    worker_max_attempts_default: int = Field(3, ge=1)

    # ---- Runtime filesystem ------------------------------------------------
    data_dir: Path = Field(default=Path("data"))
    worker_runs_dir: Path = Field(default=Path("/tmp/ade-runs"))
    # Storage (Azure Blob only)
    blob_account_url: AnyHttpUrl | None = Field(default=None)
    blob_connection_string: str | None = Field(default=None)
    blob_container: str | None = Field(default=None)
    blob_prefix: str = Field(default="workspaces")
    blob_require_versioning: bool = Field(default=True)
    blob_request_timeout_seconds: float = Field(
        default=30.0, gt=0
    )
    blob_max_concurrency: int = Field(default=4, ge=1)
    blob_upload_chunk_size_bytes: int = Field(
        default=4 * 1024 * 1024, ge=1
    )
    blob_download_chunk_size_bytes: int = Field(
        default=1024 * 1024, ge=1
    )
    # NOTE: Using @main until ade-engine tags are published.
    engine_spec: str = Field(
        default="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        validation_alias="ADE_ENGINE_PACKAGE_PATH",
    )

    # ---- Timeouts ----------------------------------------------------------
    worker_env_build_timeout_seconds: int = Field(600, ge=1)
    worker_run_timeout_seconds: int | None = None

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if not self.blob_container:
            raise ValueError("ADE_BLOB_CONTAINER is required.")
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError("ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required.")

        return self

    @property
    def venvs_dir(self) -> Path:
        return self.data_dir / "venvs"

    def backoff_seconds(self, attempt_count: int) -> int:
        base = max(0, int(self.worker_backoff_base_seconds))
        delay = base * (2 ** max(attempt_count - 1, 0))
        return min(int(self.worker_backoff_max_seconds), int(delay))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
