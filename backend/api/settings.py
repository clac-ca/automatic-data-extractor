"""Application settings for the ADE FastAPI backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """FastAPI configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    debug: bool = Field(default=False, description="Enable FastAPI debug mode.")
    app_name: str = Field(default="Automatic Data Extractor API", description="Human readable API name.")
    app_version: str = Field(default="0.1.0", description="API version string.")
    api_docs_enabled: bool = Field(default=False, description="Expose interactive API documentation endpoints.")
    docs_url: str = Field(default="/docs", description="Swagger UI mount point.")
    redoc_url: str = Field(default="/redoc", description="ReDoc mount point.")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI schema endpoint.")
    log_level: str = Field(default="INFO", description="Root log level for the backend.")

    server_host: str = Field(default="localhost", description="Hostname shared by the backend and frontend services.")
    backend_port: int = Field(default=8000, description="Port that the FastAPI backend listens on.")
    frontend_port: int = Field(default=5173, description="Port that the frontend development server listens on.")

    data_dir: Path = Field(default=PROJECT_ROOT / "backend" / "data", description="Directory for writable backend data.")
    documents_dir: Path | None = Field(default=None, description="Optional override for document storage.")
    cors_allow_origins: str = Field(
        default="",
        description="Additional CORS origins as comma separated URLs or JSON array.",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./backend/data/db/ade.sqlite",
        description="SQLAlchemy database URL.",
    )
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy engine echo logging.")
    database_pool_size: int = Field(default=5, description="SQLAlchemy connection pool size.")
    database_max_overflow: int = Field(default=10, description="SQLAlchemy connection pool overflow.")
    database_pool_timeout: int = Field(default=30, description="SQLAlchemy pool timeout in seconds.")

    auth_token_secret: str = Field(default="development-secret", description="HMAC secret for auth tokens.")
    auth_token_algorithm: str = Field(default="HS256", description="Algorithm used for JWT signing.")
    auth_access_token_ttl_minutes: int = Field(default=60, description="Access token lifetime in minutes.")
    auth_refresh_token_ttl_days: int = Field(default=14, description="Refresh token lifetime in days.")
    session_cookie_name: str = Field(default="ade_session", description="Name of the session cookie.")
    refresh_cookie_name: str = Field(default="ade_refresh", description="Name of the refresh cookie.")
    csrf_cookie_name: str = Field(default="ade_csrf", description="Name of the CSRF cookie.")
    auth_cookie_domain: str | None = Field(default=None, description="Optional cookie domain override.")
    auth_cookie_path: str = Field(default="/", description="Cookie path scope.")

    sso_client_id: str | None = Field(default=None, description="OIDC client identifier.")
    sso_client_secret: str | None = Field(default=None, description="OIDC client secret.")
    sso_issuer: str | None = Field(default=None, description="OIDC issuer URL.")
    sso_redirect_url: str | None = Field(default=None, description="OIDC redirect URL.")
    sso_scopes: str = Field(default="openid email profile", description="OIDC scopes requested.")
    sso_resource_audience: str | None = Field(default=None, description="OIDC resource audience.")

    api_key_last_seen_interval_seconds: int = Field(
        default=300,
        description="Minimum seconds between API key last-seen updates.",
    )
    max_upload_size_bytes: int = Field(
        default=25 * 1024 * 1024,
        description="Maximum upload size in bytes.",
    )
    default_document_retention_days: int = Field(default=30, description="Default document retention period in days.")

    @property
    def backend_origin(self) -> str:
        """Return the base HTTP origin for the FastAPI backend."""

        return f"http://{self.server_host}:{self.backend_port}"

    @property
    def frontend_origin(self) -> str:
        """Return the base HTTP origin for the frontend development server."""

        return f"http://{self.server_host}:{self.frontend_port}"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Return a normalised list of allowed CORS origins."""

        origins = {self.backend_origin, self.frontend_origin}

        raw = self.cors_allow_origins.strip()
        if raw:
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = []
                else:
                    if isinstance(parsed, list):
                        for item in parsed:
                            candidate = str(item).strip()
                            if candidate:
                                origins.add(candidate)
            else:
                for item in raw.split(","):
                    candidate = item.strip()
                    if candidate:
                        origins.add(candidate)

        return sorted(origins)

    @field_validator(
        "sso_client_id",
        "sso_client_secret",
        "sso_issuer",
        "sso_redirect_url",
        "sso_resource_audience",
        "auth_cookie_domain",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("server_host", mode="before")
    @classmethod
    def _normalise_host(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("server_host must not be empty")
        return host

    @field_validator("sso_scopes", mode="before")
    @classmethod
    def _normalise_scope(cls, value: str) -> str:
        scopes = " ".join(part for part in value.split() if part)
        if not scopes:
            raise ValueError("sso_scopes must not be empty")
        return scopes

    @model_validator(mode="after")
    def _finalise(self) -> Settings:
        self.data_dir = Path(self.data_dir).resolve()
        documents_dir = self.documents_dir or self.data_dir / "documents"
        self.documents_dir = Path(documents_dir).resolve()
        return self

    @property
    def sso_enabled(self) -> bool:
        """Return True when all mandatory SSO settings are present."""

        return all((self.sso_client_id, self.sso_client_secret, self.sso_issuer, self.sso_redirect_url))


def get_settings() -> Settings:
    """Return application settings loaded from the environment."""

    return Settings()


def reload_settings() -> Settings:
    """Reload settings from the environment (alias for :func:`get_settings`)."""

    return get_settings()


@runtime_checkable
class SupportsState(Protocol):
    """Objects carrying a Starlette-style ``state`` attribute."""

    state: Any


def get_app_settings(container: SupportsState) -> Settings:
    """Return settings stored on ``container.state``, initialising if absent."""

    settings = getattr(container.state, "settings", None)
    if isinstance(settings, Settings):
        return settings

    settings = get_settings()
    container.state.settings = settings
    return settings


__all__ = ["Settings", "get_settings", "reload_settings", "get_app_settings"]


