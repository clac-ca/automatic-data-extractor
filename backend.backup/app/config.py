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
    sso_client_id: str | None = Field(
        default=None,
        description="OIDC client identifier for single sign-on",
    )
    sso_client_secret: str | None = Field(
        default=None,
        description="OIDC client secret used during the token exchange",
    )
    sso_issuer: str | None = Field(
        default=None,
        description="OIDC issuer URL providing discovery metadata",
    )
    sso_redirect_url: str | None = Field(
        default=None,
        description="Redirect URL registered with the identity provider",
    )
    sso_scope: str = Field(
        default="openid email profile",
        description="Space separated scopes requested during SSO login",
    )
    sso_resource_audience: str | None = Field(
        default=None,
        description="Expected audience claim for provider access tokens",
    )
    api_key_touch_interval_seconds: int = Field(
        default=300,
        ge=0,
        description="Minimum seconds between API key last-seen updates",
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

    @field_validator(
        "sso_client_id",
        "sso_client_secret",
        "sso_issuer",
        "sso_redirect_url",
        "sso_resource_audience",
    )
    @classmethod
    def _strip_blank_sso(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("sso_scope")
    @classmethod
    def _normalise_scope(cls, value: str) -> str:
        candidate = " ".join(part for part in value.split() if part)
        if not candidate:
            raise ValueError("sso_scope must not be empty")
        return candidate

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        if "documents_dir" not in self.model_fields_set:
            self.documents_dir = self.data_dir / "documents"

        if "database_url" not in self.model_fields_set:
            default_sqlite = self.data_dir / "db" / "ade.sqlite"
            self.database_url = f"sqlite:///{default_sqlite}"

        if self.sso_client_id or self.sso_client_secret or self.sso_issuer or self.sso_redirect_url:
            required = [
                self.sso_client_id,
                self.sso_issuer,
                self.sso_redirect_url,
            ]
            if any(item is None for item in required):
                msg = "Incomplete SSO configuration; client_id, issuer, and redirect_url are required"
                raise ValueError(msg)
            if self.sso_client_secret is None:
                msg = "sso_client_secret must be set for confidential SSO flows"
                raise ValueError(msg)

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
    def sso_enabled(self) -> bool:
        """Return ``True`` when single sign-on is configured."""

        return bool(
            self.sso_client_id
            and self.sso_client_secret
            and self.sso_issuer
            and self.sso_redirect_url
        )

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
