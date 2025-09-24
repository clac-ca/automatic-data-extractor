"""Application settings and configuration helpers."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import InitSettingsSource

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SETTINGS_FILES: tuple[str, ...] = (".settings.toml", "settings.toml")
DEFAULT_SECRETS_FILES: tuple[str, ...] = (".secrets.toml",)
SETTINGS_FILES_ENV_VAR = "ADE_SETTINGS_FILES"
SECRETS_FILES_ENV_VAR = "ADE_SECRETS_FILES"
ENVIRONMENT_VARIABLES: tuple[str, ...] = ("ADE_ENV", "ADE_APP_ENV", "APP_ENV")


class AppSettings(BaseSettings):
    """Top-level FastAPI application configuration."""

    data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Root directory for persisted ADE state.",
    )
    documents_dir: Path | None = Field(
        default=None,
        description="Directory for uploaded and generated documents.",
    )
    environment: str = Field(
        default="local",
        description="Current runtime environment name.",
    )
    debug: bool = Field(
        default=False,
        description="Enable FastAPI debug mode.",
    )
    app_name: str = Field(
        default="Automatic Data Extractor API",
        description="Displayed API title.",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Semantic version exposed via OpenAPI.",
    )
    enable_docs: bool = Field(
        default=True,
        description="Expose Swagger and ReDoc routes when true.",
    )
    docs_url: str = Field(
        default="/docs",
        description="Relative path to Swagger UI.",
    )
    redoc_url: str = Field(
        default="/redoc",
        description="Relative path to ReDoc documentation.",
    )
    openapi_url: str = Field(
        default="/openapi.json",
        description="Relative path to the OpenAPI schema.",
    )
    log_level: str = Field(
        default="INFO",
        description="Python logging level for the root logger.",
    )
    cors_allow_origins: list[str] = Field(
        default_factory=list,
        description="Optional CORS allowlist for future middleware wiring.",
    )
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/db/ade.sqlite",
        description="SQLAlchemy database URL using an async driver.",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL emitted by SQLAlchemy (development aid).",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        description="Maximum number of persistent connections in the pool.",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        description="Additional connections permitted above the pool size.",
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait for a free connection before timing out.",
    )
    auth_token_secret: str = Field(
        default="development-secret",
        description="Symmetric secret used to sign authentication tokens.",
    )
    auth_token_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm for issued tokens.",
    )
    auth_token_exp_minutes: int = Field(
        default=60,
        ge=1,
        description="Minutes before issued access tokens expire.",
    )
    sso_client_id: str | None = Field(
        default=None,
        description="OIDC client identifier used during SSO flows.",
    )
    sso_client_secret: str | None = Field(
        default=None,
        description="Client secret used when exchanging authorization codes.",
    )
    sso_issuer: str | None = Field(
        default=None,
        description="OIDC issuer URL providing discovery metadata.",
    )
    sso_redirect_url: str | None = Field(
        default=None,
        description="Callback URL registered with the identity provider.",
    )
    sso_scope: str = Field(
        default="openid email profile",
        description="Space-separated scopes requested during SSO login.",
    )
    sso_resource_audience: str | None = Field(
        default=None,
        description="Optional resource audience expected on provider access tokens.",
    )
    api_key_touch_interval_seconds: int = Field(
        default=300,
        ge=0,
        description="Minimum seconds between API key last-seen updates.",
    )
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1,
        description="Maximum accepted upload size for POST /documents in bytes.",
    )
    default_document_retention_days: int = Field(
        default=30,
        ge=1,
        description="Default number of days to retain uploaded documents before expiry.",
    )

    model_config = SettingsConfigDict(
        env_prefix="ADE_",
        env_nested_delimiter="__",
        env_file=(".env",),
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def docs_urls(self) -> tuple[str | None, str | None]:
        """Return the docs and redoc URLs respecting the `enable_docs` flag."""

        if not self.enable_docs:
            return None, None
        return self.docs_url, self.redoc_url

    @property
    def sso_enabled(self) -> bool:
        """Return True when single sign-on is fully configured."""

        return bool(
            self.sso_client_id
            and self.sso_client_secret
            and self.sso_issuer
            and self.sso_redirect_url
        )

    @field_validator(
        "sso_client_id",
        "sso_client_secret",
        "sso_issuer",
        "sso_redirect_url",
        "sso_resource_audience",
        mode="before",
    )
    @classmethod
    def _strip_blank_sso(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("sso_scope", mode="before")
    @classmethod
    def _normalise_scope(cls, value: str) -> str:
        candidate = " ".join(part for part in value.split() if part)
        if not candidate:
            raise ValueError("sso_scope must not be empty")
        return candidate

    @model_validator(mode="after")
    def _derive_directories(self) -> AppSettings:
        """Resolve dependent filesystem paths after initial parsing."""

        self.data_dir = Path(self.data_dir).resolve()
        documents_dir = self.documents_dir
        if documents_dir is None:
            documents_dir = self.data_dir / "documents"
        self.documents_dir = Path(documents_dir).resolve()
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: InitSettingsSource,
        dotenv_settings: InitSettingsSource,
        file_secret_settings: InitSettingsSource,
    ) -> tuple[InitSettingsSource, ...]:
        """Load settings from env vars, optional TOML files, then filesystem secrets."""

        environment = _resolve_environment(settings_cls)
        settings_files = _resolve_files(SETTINGS_FILES_ENV_VAR, DEFAULT_SETTINGS_FILES)
        secrets_files = _resolve_files(SECRETS_FILES_ENV_VAR, DEFAULT_SECRETS_FILES)

        sources: list[InitSettingsSource] = [init_settings, env_settings, dotenv_settings]

        if settings_files:
            sources.append(_build_toml_source(settings_cls, settings_files, environment))
        if secrets_files:
            sources.append(_build_toml_source(settings_cls, secrets_files, environment))

        sources.append(file_secret_settings)
        return tuple(sources)


def _resolve_environment(settings_cls: type[BaseSettings]) -> str:
    """Resolve the desired configuration environment name."""

    for env_var in ENVIRONMENT_VARIABLES:
        env_value = os.getenv(env_var)
        if env_value:
            return env_value

    field = settings_cls.model_fields.get("environment")
    if field and field.default is not None:
        return str(field.default)
    return "local"


def _resolve_files(env_var: str, defaults: Iterable[str]) -> list[Path]:
    """Resolve configuration file paths from overrides or defaults."""

    override = os.getenv(env_var)
    if override:
        candidates = [segment.strip() for segment in override.split(",") if segment.strip()]
    else:
        candidates = list(defaults)

    resolved_paths: list[Path] = []
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.is_file():
            resolved_paths.append(path)
    return resolved_paths


def _build_toml_source(
    settings_cls: type[BaseSettings],
    files: list[Path],
    environment: str,
) -> InitSettingsSource:
    """Create an InitSettingsSource from the merged TOML configuration files."""

    values: dict[str, Any] = {}
    for file in files:
        values.update(_load_toml_values(file, environment))

    if values and "environment" not in values:
        values["environment"] = environment

    return InitSettingsSource(settings_cls, values)


def _load_toml_values(file_path: Path, environment: str) -> dict[str, Any]:
    """Merge default and environment-specific TOML sections."""

    with file_path.open("rb") as handle:
        data = tomllib.load(handle)

    merged: dict[str, Any] = {}
    default_block = data.get("default")
    if isinstance(default_block, dict):
        merged.update(default_block)

    env_block = data.get(environment)
    if isinstance(env_block, dict):
        merged.update(env_block)

    for key, value in data.items():
        if key in {"default", environment}:
            continue
        if isinstance(value, dict):
            continue
        merged[key] = value

    return merged


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached application settings instance."""

    return AppSettings()


def reset_settings_cache() -> None:
    """Clear the cached settings to force a reload on next access."""

    get_settings.cache_clear()


__all__ = [
    "AppSettings",
    "get_settings",
    "reset_settings_cache",
]
