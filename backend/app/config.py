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
    auth_modes: str = Field(
        default="basic",
        description=(
            "Comma separated list of enabled authentication mechanisms (none, basic, sso)"
        ),
    )
    session_cookie_name: str = Field(
        default="ade_session",
        min_length=1,
        description="Name of the browser cookie carrying session tokens",
    )
    session_ttl_minutes: int = Field(
        default=720,
        gt=0,
        description="Validity window for issued browser sessions",
    )
    session_cookie_secure: bool = Field(
        default=False,
        description="Mark session cookies as Secure (HTTPS-only)",
    )
    session_cookie_domain: str | None = Field(
        default=None,
        description="Optional domain attribute to include on session cookies",
    )
    session_cookie_path: str = Field(
        default="/",
        description="Path attribute applied to session cookies",
    )
    session_cookie_same_site: str = Field(
        default="lax",
        description="SameSite attribute for session cookies (lax, strict, none)",
    )
    sso_client_id: str | None = Field(default=None, description="OIDC client identifier")
    sso_client_secret: str | None = Field(
        default=None, description="OIDC client secret for code exchange"
    )
    sso_issuer: str | None = Field(
        default=None,
        description="OIDC issuer base URL used for discovery",
    )
    sso_redirect_url: str | None = Field(
        default=None,
        description="Callback URL registered with the OIDC provider",
    )
    sso_audience: str | None = Field(
        default=None,
        description="Expected ID token audience (defaults to client id when unset)",
    )
    sso_scopes: str = Field(
        default="openid email profile",
        description="Scopes requested during the OIDC authorisation redirect",
    )
    sso_cache_ttl_seconds: int = Field(
        default=300,
        gt=0,
        description="Seconds to cache discovery documents and JWKS responses",
    )
    sso_auto_provision: bool = Field(
        default=False,
        description="Automatically create users for valid SSO identities",
    )
    admin_email_allowlist_enabled: bool = Field(
        default=False,
        description="Require administrator accounts to match the configured allowlist",
    )
    admin_email_allowlist: str | None = Field(
        default=None,
        description="Comma separated list of administrator email addresses",
    )

    @field_validator("session_cookie_same_site")
    @classmethod
    def _validate_same_site(cls, value: str) -> str:
        candidate = value.lower().strip()
        if candidate not in {"lax", "strict", "none"}:
            msg = "session_cookie_same_site must be lax, strict, or none"
            raise ValueError(msg)
        return candidate

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
    def auth_mode_sequence(self) -> tuple[str, ...]:
        """Return configured authentication modes in declaration order."""

        modes: list[str] = []
        allowed = {"none", "basic", "sso"}
        for raw in self.auth_modes.split(","):
            candidate = raw.strip().lower()
            if not candidate:
                continue
            if candidate not in allowed:
                msg = f"Unsupported auth mode: {candidate}"
                raise ValueError(msg)
            if candidate not in modes:
                modes.append(candidate)

        if not modes:
            raise ValueError("At least one authentication mode must be specified")

        if "none" in modes:
            if len(modes) > 1:
                raise ValueError("Auth mode 'none' cannot be combined with other modes")
            return ("none",)

        return tuple(modes)

    @property
    def admin_allowlist(self) -> tuple[str, ...]:
        """Return normalised administrator email addresses."""

        source = (self.admin_email_allowlist or "").strip()
        if not source:
            return ()

        values: list[str] = []
        for item in source.split(","):
            candidate = item.strip().lower()
            if candidate and candidate not in values:
                values.append(candidate)
        return tuple(values)

    @model_validator(mode="after")
    def _apply_derived_paths(self) -> "Settings":
        """Derive dependent filesystem locations when unset."""

        if "documents_dir" not in self.model_fields_set:
            self.documents_dir = self.data_dir / "documents"

        if "database_url" not in self.model_fields_set:
            default_sqlite = self.data_dir / "db" / "ade.sqlite"
            self.database_url = f"sqlite:///{default_sqlite}"

        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings so future calls re-read the environment."""

    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
