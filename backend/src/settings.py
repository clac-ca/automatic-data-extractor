"""Shared settings helpers and mixins for ADE services."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from paths import REPO_ROOT

ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
ALLOWED_LOG_FORMATS = frozenset({"console", "json"})
DEFAULT_DATA_DIR = REPO_ROOT / "backend" / "data"


def ade_settings_config(
    *,
    enable_decoding: bool = True,
    populate_by_name: bool = False,
) -> SettingsConfigDict:
    """Return the standard ADE ``BaseSettings`` config dict."""

    return SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        enable_decoding=enable_decoding,
        populate_by_name=populate_by_name,
        str_strip_whitespace=True,
    )


def create_settings_accessors[T](
    settings_type: type[T],
) -> tuple[Callable[[], T], Callable[[], T]]:
    """Create ``get_settings`` and ``reload_settings`` helpers for a settings class."""

    @lru_cache(maxsize=1)
    def _build() -> T:
        return settings_type()

    def get_settings() -> T:
        return _build()

    def reload_settings() -> T:
        _build.cache_clear()
        return _build()

    return get_settings, reload_settings


def normalize_log_format(value: str, *, env_var: str = "ADE_LOG_FORMAT") -> str:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_LOG_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_LOG_FORMATS))
        raise ValueError(f"{env_var} must be one of: {allowed}.")
    return normalized


def normalize_log_level(value: str | None, *, env_var: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized not in ALLOWED_LOG_LEVELS:
        allowed = ", ".join(sorted(ALLOWED_LOG_LEVELS))
        raise ValueError(f"{env_var} must be one of: {allowed}.")
    return normalized


class DatabaseSettingsMixin:
    """Shared database settings used by API, worker, and DB tooling."""

    database_url: PostgresDsn = Field(..., description="Postgres database URL.")
    database_echo: bool = False
    database_auth_mode: Literal["password", "managed_identity"] = "password"
    database_sslrootcert: str | None = Field(default=None)
    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)
    database_connect_timeout_seconds: int | None = Field(default=10, ge=0)
    database_statement_timeout_ms: int | None = Field(default=30_000, ge=0)


class DatabaseSettingsProtocol(Protocol):
    """Structural type for database settings consumed across service boundaries."""

    database_url: PostgresDsn | str
    database_echo: bool
    database_auth_mode: str
    database_sslrootcert: str | None
    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout: int
    database_pool_recycle: int
    database_connect_timeout_seconds: int | None
    database_statement_timeout_ms: int | None


class BlobStorageSettingsMixin:
    """Shared blob storage settings used by API, worker, and storage tooling."""

    blob_account_url: str | None = Field(default=None)
    blob_connection_string: str | None = Field(default=None)
    blob_container: str = Field(default="ade")
    blob_prefix: str = Field(default="workspaces")
    blob_versioning_mode: Literal["auto", "require", "off"] = Field(default="auto")
    blob_request_timeout_seconds: float = Field(default=30.0, gt=0)
    blob_max_concurrency: int = Field(default=4, ge=1)
    blob_upload_chunk_size_bytes: int = Field(default=4 * 1024 * 1024, ge=1)
    blob_download_chunk_size_bytes: int = Field(default=1024 * 1024, ge=1)

    @field_validator("blob_versioning_mode", mode="before")
    @classmethod
    def _normalize_blob_versioning_mode(cls, value: object) -> object:
        if value is None:
            return "auto"
        raw = str(value).strip().lower()
        if raw in {"auto", "require", "off"}:
            return raw
        raise ValueError("ADE_BLOB_VERSIONING_MODE must be one of: auto, require, off.")

    @model_validator(mode="after")
    def _validate_blob_settings(self) -> BlobStorageSettingsMixin:
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError("ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required.")
        if self.blob_account_url:
            self.blob_account_url = self.blob_account_url.rstrip("/")
        if self.blob_prefix:
            self.blob_prefix = self.blob_prefix.strip("/")
        return self


class BlobStorageSettingsProtocol(Protocol):
    """Structural type for blob storage settings consumed across package boundaries."""

    blob_account_url: str | None
    blob_connection_string: str | None
    blob_container: str
    blob_prefix: str
    blob_versioning_mode: Literal["auto", "require", "off"]
    blob_request_timeout_seconds: float
    blob_max_concurrency: int
    blob_upload_chunk_size_bytes: int
    blob_download_chunk_size_bytes: int


class StorageLayoutSettingsProtocol(Protocol):
    """Structural type for filesystem layout settings used by storage helpers."""

    workspaces_dir: Path
    configs_dir: Path
    runs_dir: Path
    documents_dir: Path
    venvs_dir: Path


class DataPathsSettingsMixin:
    """Shared ADE data-root and derived filesystem paths."""

    data_dir: Path = Field(default=DEFAULT_DATA_DIR)

    @field_validator("data_dir", mode="before")
    @classmethod
    def _resolve_data_dir(cls, value: object) -> object:
        if value is None:
            return DEFAULT_DATA_DIR
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.resolve()

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
    def venvs_dir(self) -> Path:
        return self.data_dir / "venvs"

    @property
    def pip_cache_dir(self) -> Path:
        return self.data_dir / "cache" / "pip"


__all__ = [
    "ALLOWED_LOG_FORMATS",
    "ALLOWED_LOG_LEVELS",
    "DEFAULT_DATA_DIR",
    "BlobStorageSettingsMixin",
    "BlobStorageSettingsProtocol",
    "DataPathsSettingsMixin",
    "DatabaseSettingsProtocol",
    "DatabaseSettingsMixin",
    "StorageLayoutSettingsProtocol",
    "ade_settings_config",
    "create_settings_accessors",
    "normalize_log_format",
    "normalize_log_level",
]
