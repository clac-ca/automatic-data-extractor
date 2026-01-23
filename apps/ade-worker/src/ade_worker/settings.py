"""ADE Worker settings (Pydantic v2, clean-slate)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

MODULE_DIR = Path(__file__).resolve().parent


def _detect_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "apps").is_dir():
            return p
        if (p / ".git").is_dir():
            return p
    return Path.cwd()


REPO_ROOT = _detect_repo_root(MODULE_DIR)


def _default_concurrency() -> int:
    cpu = os.cpu_count() or 2
    return max(1, min(4, cpu // 2))


class Settings(BaseSettings):
    """Worker settings loaded from ADE_* env vars (and repo-root .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    _database_url: str = PrivateAttr(default="")

    # ---- Database (match ade-api field names) ------------------------------
    database_url_override: str | None = None
    database_echo: bool = False

    database_auth_mode: Literal["sql_password", "managed_identity"] = "sql_password"
    database_mi_client_id: str | None = None

    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)

    database_sqlite_journal_mode: Literal[
        "WAL",
        "DELETE",
        "TRUNCATE",
        "PERSIST",
        "MEMORY",
        "OFF",
    ] = "WAL"
    database_sqlite_synchronous: Literal["OFF", "NORMAL", "FULL", "EXTRA"] = "NORMAL"
    database_sqlite_busy_timeout_ms: int = Field(30_000, ge=0)
    database_sqlite_begin_mode: Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"] | None = None

    # ---- Database (derived mssql URL inputs) ------------------------------
    sql_host: str = "sql"
    sql_port: int = Field(default=1433, ge=1, le=65535)
    sql_user: str = "sa"
    sql_password: str = "YourStrong!Passw0rd"
    sql_database: str = "ade"
    sql_encrypt: str = "optional"
    sql_trust_server_certificate: str = "yes"

    # ---- Worker identity & loop -------------------------------------------
    worker_id: str | None = None
    worker_concurrency: int = Field(default_factory=_default_concurrency, ge=1)
    worker_poll_interval: float = Field(0.5, gt=0)
    worker_poll_interval_max: float = Field(2.0, gt=0)
    worker_cleanup_interval: float = Field(30.0, gt=0)
    worker_log_level: str = "INFO"

    # ---- Garbage collection ------------------------------------------------
    worker_enable_gc: bool = True
    worker_gc_interval_seconds: float = Field(3600.0, gt=0)
    worker_env_ttl_days: int = Field(30, ge=0)
    worker_run_artifact_ttl_days: int | None = Field(30, ge=0)

    # ---- Queue leasing / retries ------------------------------------------
    worker_lease_seconds: int = Field(900, ge=1)
    worker_backoff_base_seconds: int = Field(5, ge=0)
    worker_backoff_max_seconds: int = Field(300, ge=0)
    worker_max_attempts_default: int = Field(3, ge=1)

    # ---- Runtime filesystem ------------------------------------------------
    data_dir: Path = Field(default=REPO_ROOT / "data")
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

    @field_validator("database_url_override", mode="before")
    @classmethod
    def _v_database_url_override(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip()

    @field_validator("database_auth_mode", mode="before")
    @classmethod
    def _v_db_auth_mode(cls, v: Any) -> str:
        if v in (None, ""):
            return "sql_password"
        mode = str(v).strip().lower()
        if mode not in {"sql_password", "managed_identity"}:
            raise ValueError("ADE_DATABASE_AUTH_MODE must be 'sql_password' or 'managed_identity'")
        return mode

    @field_validator("database_sqlite_journal_mode", "database_sqlite_synchronous", mode="before")
    @classmethod
    def _v_sqlite_pragma_enum(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip().upper()

    @field_validator("database_sqlite_begin_mode", mode="before")
    @classmethod
    def _v_sqlite_begin_mode(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip().upper()

    @field_validator(
        "sql_host",
        "sql_user",
        "sql_password",
        "sql_database",
        "sql_encrypt",
        "sql_trust_server_certificate",
        mode="before",
    )
    @classmethod
    def _v_sql_str(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip()

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if not self.data_dir.is_absolute():
            self.data_dir = (REPO_ROOT / self.data_dir).resolve()
        else:
            self.data_dir = self.data_dir.expanduser().resolve()

        if self.database_url_override:
            url = make_url(self.database_url_override)
        else:
            sql_vars = {
                "host": self.sql_host,
                "user": self.sql_user,
                "password": self.sql_password,
                "database": self.sql_database,
            }
            if self.database_auth_mode == "managed_identity":
                required = ["host", "database"]
            else:
                required = ["host", "user", "password", "database"]

            missing = [key for key in required if not sql_vars[key]]
            if missing:
                raise ValueError(
                    "Missing required ADE_SQL_* values: "
                    + ", ".join(f"ADE_SQL_{name.upper()}" for name in missing)
                )

            query = {"driver": "ODBC Driver 18 for SQL Server"}
            if self.sql_encrypt:
                query["Encrypt"] = self.sql_encrypt
            if self.sql_trust_server_certificate:
                query["TrustServerCertificate"] = self.sql_trust_server_certificate

            if self.database_auth_mode == "managed_identity":
                url = URL.create(
                    drivername="mssql+pyodbc",
                    username=None,
                    password=None,
                    host=self.sql_host,
                    port=self.sql_port,
                    database=self.sql_database,
                    query=query,
                )
            else:
                url = URL.create(
                    drivername="mssql+pyodbc",
                    username=self.sql_user,
                    password=self.sql_password,
                    host=self.sql_host,
                    port=self.sql_port,
                    database=self.sql_database,
                    query=query,
                )

        url = make_url(url.render_as_string(hide_password=False))
        query = dict(url.query or {})

        if (
            url.get_backend_name() == "sqlite"
            and "database_sqlite_busy_timeout_ms" not in self.model_fields_set
        ):
            self.database_sqlite_busy_timeout_ms = int(self.database_pool_timeout * 1000)

        if url.get_backend_name() == "mssql":
            present = {k.lower() for k in query}

            def _setdefault_ci(key: str, value: str) -> None:
                if key.lower() not in present:
                    query[key] = value
                    present.add(key.lower())

            _setdefault_ci("driver", "ODBC Driver 18 for SQL Server")
            if self.sql_encrypt:
                _setdefault_ci("Encrypt", self.sql_encrypt)
            if self.sql_trust_server_certificate:
                _setdefault_ci("TrustServerCertificate", self.sql_trust_server_certificate)

        if self.database_auth_mode == "managed_identity":
            if url.get_backend_name() != "mssql":
                raise ValueError("managed_identity requires an mssql+pyodbc URL")
            url = URL.create(
                drivername=url.drivername,
                username=None,
                password=None,
                host=url.host,
                port=url.port,
                database=url.database,
                query=query,
            )
        elif query != url.query:
            url = url.set(query=query)

        self._database_url = url.render_as_string(hide_password=False)

        if self.worker_run_artifact_ttl_days is not None and self.worker_run_artifact_ttl_days <= 0:
            self.worker_run_artifact_ttl_days = None
        if self.worker_run_timeout_seconds is not None and self.worker_run_timeout_seconds <= 0:
            self.worker_run_timeout_seconds = None

        return self

    @property
    def database_url(self) -> str:
        return self._database_url

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
