"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---- Defaults ---------------------------------------------------------------

DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 2000
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
MAX_SET_SIZE = 50  # cap for *_in lists
COUNT_STATEMENT_TIMEOUT_MS: int | None = None  # optional (Postgres), e.g., 500


# ---- Settings ---------------------------------------------------------------


class Settings(BaseSettings):
    """FastAPI settings loaded from ADE_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        populate_by_name=True,
        env_parse_delimiter=",",
        str_strip_whitespace=True,
    )

    # Core
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "1.6.1"
    app_commit_sha: str = "unknown"
    api_docs_enabled: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    log_level: str = "INFO"
    safe_mode: bool = False

    # Server
    server_public_url: str = DEFAULT_PUBLIC_URL
    api_host: str | None = None
    api_port: int | None = Field(default=None, ge=1, le=65535)
    api_workers: int | None = Field(default=None, ge=1)
    frontend_url: str | None = None
    frontend_dist_dir: Path | None = Field(default=None)
    server_cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))
    idempotency_key_ttl: timedelta = Field(default=timedelta(hours=24))

    # Paths
    api_root: Path = Field(default=Path("apps/ade-api"))
    alembic_ini_path: Path = Field(default=Path("apps/ade-api/alembic.ini"))
    alembic_migrations_dir: Path = Field(default=Path("apps/ade-api/migrations"))

    # Storage
    data_dir: Path = Field(default=Path("data"))
    blob_account_url: str | None = Field(default=None)
    blob_connection_string: str | None = Field(default=None)
    blob_container: str | None = Field(default=None)
    blob_prefix: str = Field(default="workspaces")
    blob_require_versioning: bool = Field(default=True)
    blob_request_timeout_seconds: float = Field(default=30.0, gt=0)
    blob_max_concurrency: int = Field(default=4, ge=1)
    blob_upload_chunk_size_bytes: int = Field(default=4 * 1024 * 1024, ge=1)
    blob_download_chunk_size_bytes: int = Field(default=1024 * 1024, ge=1)
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    documents_upload_concurrency_limit: int | None = Field(8, ge=1)

    # Engine
    engine_spec: str = Field(default="ade-engine @ git+https://github.com/clac-ca/ade-engine@main")

    # Database
    database_url: PostgresDsn = Field(..., description="Postgres database URL.")
    database_echo: bool = False
    database_log_level: str | None = None
    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)
    database_auth_mode: Literal["password", "managed_identity"] = "password"
    database_sslrootcert: str | None = Field(default=None)
    document_changes_retention_days: int = Field(default=14, ge=1)

    # JWT
    secret_key: SecretStr = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(30, ge=1)

    # Sessions
    session_cookie_name: str = "ade_session"
    session_csrf_cookie_name: str = "ade_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_access_ttl: timedelta = Field(default=timedelta(days=14))

    # Auth policy
    api_key_prefix_length: int = Field(12, ge=6, le=32)
    api_key_secret_bytes: int = Field(32, ge=16, le=128)
    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))
    allow_public_registration: bool = False
    auth_disabled: bool = False
    auth_disabled_user_email: str = "developer@example.com"
    auth_disabled_user_name: str | None = "Development User"
    auth_force_sso: bool = False
    auth_sso_auto_provision: bool = False
    auth_sso_providers_json: str | None = None
    sso_encryption_key: SecretStr | None = None

    # Runs
    preview_timeout_seconds: float = Field(10, gt=0)

    # ---- Validators ----

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if self.algorithm != "HS256":
            raise ValueError("ADE_ALGORITHM must be HS256.")
        if len(self.secret_key.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("ADE_SECRET_KEY must be at least 32 bytes (recommend 64+).")
        if not self.blob_container:
            raise ValueError("ADE_BLOB_CONTAINER is required.")
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required."
            )

        return self

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def documents_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def configs_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def runs_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def venvs_dir(self) -> Path:
        return self.data_dir / "venvs"

    @property
    def pip_cache_dir(self) -> Path:
        return self.data_dir / "cache" / "pip"

    # ---- Convenience ----

    @property
    def secret_key_value(self) -> str:
        return self.secret_key.get_secret_value()


@lru_cache(maxsize=1)
def _build_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    return _build_settings()


def reload_settings() -> Settings:
    _build_settings.cache_clear()
    return _build_settings()


__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_PUBLIC_URL",
    "Settings",
    "get_settings",
    "reload_settings",
]
