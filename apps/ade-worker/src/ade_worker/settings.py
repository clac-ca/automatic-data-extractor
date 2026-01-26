"""ADE Worker settings (Pydantic v2, clean-slate)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

MODULE_DIR = Path(__file__).resolve().parent


def _detect_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "apps").is_dir():
            return p
        if (p / ".git").is_dir():
            return p
    return Path.cwd()


REPO_ROOT = _detect_repo_root(MODULE_DIR)

DEFAULT_DATABASE_URL = "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable"
DEFAULT_DATABASE_AUTH_MODE = "password"
DEFAULT_BLOB_PREFIX = "workspaces"
DEFAULT_BLOB_REQUIRE_VERSIONING = True
DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP = False
DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_BLOB_MAX_CONCURRENCY = 4
DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES = 4 * 1024 * 1024  # 4 MiB
DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MiB


def _default_concurrency() -> int:
    cpu = os.cpu_count() or 2
    return max(1, min(4, cpu // 2))


def _normalize_pg_driver(drivername: str) -> str:
    if drivername in {"postgres", "postgresql"}:
        return "postgresql+psycopg"
    if drivername.startswith("postgresql+") and drivername != "postgresql+psycopg":
        return "postgresql+psycopg"
    return drivername


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
    )

    # ---- Database (match ade-api field names) ------------------------------
    database_url: str = Field(..., description="Postgres database URL.")
    database_echo: bool = False

    database_auth_mode: Literal["password", "managed_identity"] = Field(
        default=DEFAULT_DATABASE_AUTH_MODE
    )
    database_sslrootcert: str | None = Field(default=None)

    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)

    # ---- Worker identity & loop -------------------------------------------
    worker_id: str | None = None
    worker_concurrency: int = Field(default_factory=_default_concurrency, ge=1)
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
    data_dir: Path = Field(default=REPO_ROOT / "data")
    # Storage (Azure Blob only)
    blob_account_url: str | None = Field(default=None)
    blob_connection_string: str | None = Field(default=None)
    blob_container: str | None = Field(default=None)
    blob_prefix: str = Field(default=DEFAULT_BLOB_PREFIX)
    blob_require_versioning: bool = Field(default=DEFAULT_BLOB_REQUIRE_VERSIONING)
    blob_create_container_on_startup: bool = Field(
        default=DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP
    )
    blob_request_timeout_seconds: float = Field(
        default=DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS, gt=0
    )
    blob_max_concurrency: int = Field(default=DEFAULT_BLOB_MAX_CONCURRENCY, ge=1)
    blob_upload_chunk_size_bytes: int = Field(
        default=DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES, ge=1
    )
    blob_download_chunk_size_bytes: int = Field(
        default=DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES, ge=1
    )
    # NOTE: Using @main until ade-engine tags are published.
    engine_spec: str = Field(
        default="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        validation_alias="ADE_ENGINE_PACKAGE_PATH",
    )

    # ---- Timeouts ----------------------------------------------------------
    worker_env_build_timeout_seconds: int = Field(600, ge=1)
    worker_run_timeout_seconds: int | None = None

    # ---- Validators --------------------------------------------------------

    @field_validator("worker_log_level", mode="before")
    @classmethod
    def _v_log_level(cls, v: Any) -> str:
        return ("" if v is None else str(v).strip()).upper() or "INFO"

    @field_validator("database_url", mode="before")
    @classmethod
    def _v_database_url(cls, v: Any) -> str:
        if v in (None, ""):
            raise ValueError("ADE_DATABASE_URL is required.")
        return str(v).strip()

    @field_validator("database_sslrootcert", mode="before")
    @classmethod
    def _v_database_sslrootcert(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip()

    @field_validator("blob_account_url", mode="before")
    @classmethod
    def _v_blob_account_url(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        s = str(v).strip()
        if not s:
            return None
        p = urlparse(s)
        if p.scheme not in {"http", "https"} or not p.netloc:
            raise ValueError("ADE_BLOB_ACCOUNT_URL must be an http(s) URL")
        return s.rstrip("/")

    @field_validator("blob_connection_string", mode="before")
    @classmethod
    def _v_blob_connection_string(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("blob_container", mode="before")
    @classmethod
    def _v_blob_container(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("blob_prefix", mode="before")
    @classmethod
    def _v_blob_prefix(cls, v: Any) -> str:
        if v in (None, ""):
            return DEFAULT_BLOB_PREFIX
        cleaned = str(v).strip().strip("/")
        return cleaned or DEFAULT_BLOB_PREFIX

    @model_validator(mode="after")
    def _validate_blob_settings(self) -> "Settings":
        if not self.blob_container:
            raise ValueError("ADE_BLOB_CONTAINER is required.")
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError("ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required.")
        return self

    @field_validator("database_auth_mode", mode="before")
    @classmethod
    def _v_db_auth_mode(cls, v: Any) -> str:
        if v in (None, ""):
            return DEFAULT_DATABASE_AUTH_MODE
        mode = str(v).strip().lower()
        if mode not in {"password", "managed_identity"}:
            raise ValueError("ADE_DATABASE_AUTH_MODE must be 'password' or 'managed_identity'")
        return mode

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if not self.data_dir.is_absolute():
            self.data_dir = (REPO_ROOT / self.data_dir).resolve()
        else:
            self.data_dir = self.data_dir.expanduser().resolve()

        if not self.database_url:
            raise ValueError("ADE_DATABASE_URL is required.")

        url = make_url(self.database_url)
        drivername = _normalize_pg_driver(url.drivername)
        if not drivername.startswith("postgresql"):
            raise ValueError("Only Postgres is supported. Use postgresql+psycopg://... for ADE_DATABASE_URL.")
        if drivername != url.drivername:
            url = url.set(drivername=drivername)

        required_values = {
            "host": url.host,
            "user": url.username,
            "database": url.database,
        }
        missing = [name for name, value in required_values.items() if not value]
        if self.database_auth_mode == "password" and not url.password:
            missing.append("password")
        if missing:
            raise ValueError(
                "ADE_DATABASE_URL is missing required parts: " + ", ".join(missing)
            )

        if self.database_sslrootcert:
            query = dict(url.query or {})
            query["sslrootcert"] = self.database_sslrootcert
            url = url.set(query=query)

        self.database_url = url.render_as_string(hide_password=False)

        if self.worker_run_artifact_ttl_days is not None and self.worker_run_artifact_ttl_days <= 0:
            self.worker_run_artifact_ttl_days = None
        if self.worker_run_timeout_seconds is not None and self.worker_run_timeout_seconds <= 0:
            self.worker_run_timeout_seconds = None

        return self

    @property
    def venvs_dir(self) -> Path:
        return (self.data_dir / "venvs").resolve()

    def backoff_seconds(self, attempt_count: int) -> int:
        base = max(0, int(self.worker_backoff_base_seconds))
        delay = base * (2 ** max(attempt_count - 1, 0))
        return min(int(self.worker_backoff_max_seconds), int(delay))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
