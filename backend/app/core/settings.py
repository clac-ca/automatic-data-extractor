"""Application settings and configuration helpers."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import tomllib
from pydantic import Field
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

    environment: str = Field(default="local", description="Current runtime environment name.")
    debug: bool = Field(default=False, description="Enable FastAPI debug mode.")
    app_name: str = Field(default="Automatic Data Extractor API", description="Displayed API title.")
    app_version: str = Field(default="0.1.0", description="Semantic version exposed via OpenAPI.")
    enable_docs: bool = Field(default=True, description="Expose Swagger and ReDoc routes when true.")
    docs_url: str = Field(default="/docs", description="Relative path to Swagger UI.")
    redoc_url: str = Field(default="/redoc", description="Relative path to ReDoc documentation.")
    openapi_url: str = Field(default="/openapi.json", description="Relative path to the OpenAPI schema.")
    log_level: str = Field(default="INFO", description="Python logging level for the root logger.")
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
