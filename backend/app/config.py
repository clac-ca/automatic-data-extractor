"""Application configuration settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """Runtime configuration for the ADE backend."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADE_", extra="ignore")

    data_dir: Path = Field(
        default=Path("data"),
        description="Root directory for persisted ADE state",
    )
    database_url: str = Field(
        default="sqlite:///data/db/ade.sqlite",
        description="SQLAlchemy database URL",
    )
    documents_dir: Path = Field(
        default=Path("data/documents"),
        description="Directory for uploaded documents",
    )
    auto_migrate: bool | None = Field(
        default=None,
        description=(
            "If None, auto-apply Alembic migrations when using a file-based "
            "SQLite database. Set False to require manual upgrades."
        ),
    )
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        description="Maximum accepted upload size for POST /documents",
    )
    default_document_retention_days: int = Field(
        default=30,
        gt=0,
        description="Default number of days to keep uploaded documents before they expire",
    )
    purge_schedule_enabled: bool = Field(
        default=True,
        description="Run the automatic purge loop inside the API service",
    )
    purge_schedule_run_on_startup: bool = Field(
        default=True,
        description="Execute a purge sweep immediately when the API starts",
    )
    purge_schedule_interval_seconds: int = Field(
        default=3600,
        ge=1,
        description="Number of seconds to wait between automatic purge sweeps",
    )

    auth_disabled: bool = Field(
        default=False,
        description="Allow anonymous access to all endpoints (development only)",
    )
    jwt_secret_key: str | None = Field(
        default=None,
        description="Symmetric secret used to sign access tokens",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    access_token_exp_minutes: int = Field(
        default=60,
        ge=1,
        description="Minutes before issued access tokens expire",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def _strip_blank_secret(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_algorithm(cls, value: str) -> str:
        candidate = value.strip().upper()
        if not candidate:
            raise ValueError("jwt_algorithm must not be empty")
        return candidate

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        if "documents_dir" not in self.model_fields_set:
            self.documents_dir = self.data_dir / "documents"

        if "database_url" not in self.model_fields_set:
            default_sqlite = self.data_dir / "db" / "ade.sqlite"
            self.database_url = f"sqlite:///{default_sqlite}"

        return self

    @property
    def database_path(self) -> Path | None:
        """Return the filesystem path of the SQLite database if available."""

        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite":
            return None

        database = (url.database or "").strip()
        if not database or database == ":memory:":
            return None

        return Path(database)

    @property
    def auth_required(self) -> bool:
        """Return True when API requests must present a valid token."""

        return not self.auth_disabled

    @property
    def database_is_sqlite_memory(self) -> bool:
        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite":
            return False
        database = (url.database or "").strip()
        if not database or database == ":memory:":
            return True
        return database.startswith("file::memory:")

    @property
    def documents_path(self) -> Path:
        return self.documents_dir


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings so future calls re-read the environment."""

    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
