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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """Patch env sources so non-JSON lists can be parsed downstream."""

        def install_fallback(source: Any) -> None:
            original = source.decode_complex_value

            def decode(self, field_name: str, field: Any, value: Any, *, _original=original):
                try:
                    return _original(field_name, field, value)
                except json.JSONDecodeError:
                    if isinstance(value, str):
                        return value
                    raise

            source.decode_complex_value = decode.__get__(source, source.__class__)

        install_fallback(env_settings)
        install_fallback(dotenv_settings)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "local"
    debug: bool = False
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "0.1.0"
    enable_docs: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    docs_environment_allowlist: tuple[str, ...] = ("local", "staging")
    log_level: str = "INFO"

    data_dir: Path = PROJECT_ROOT / "backend" / "data"
    documents_dir: Path | None = None
    cors_allow_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if value is None:
            return []
        return value

    database_url: str = "sqlite+aiosqlite:///./backend/data/db/ade.sqlite"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    auth_token_secret: str = "development-secret"
    auth_token_algorithm: str = "HS256"
    auth_token_exp_minutes: int = 60
    auth_refresh_token_exp_days: int = 14
    auth_session_cookie: str = "ade_session"
    auth_refresh_cookie: str = "ade_refresh"
    auth_csrf_cookie: str = "ade_csrf"
    auth_cookie_domain: str | None = None
    auth_cookie_path: str = "/"

    sso_client_id: str | None = None
    sso_client_secret: str | None = None
    sso_issuer: str | None = None
    sso_redirect_url: str | None = None
    sso_scope: str = "openid email profile"
    sso_resource_audience: str | None = None

    api_key_touch_interval_seconds: int = 300
    max_upload_bytes: int = 25 * 1024 * 1024
    default_document_retention_days: int = 30

    @property
    def docs_enabled(self) -> bool:
        """Return whether interactive documentation should be exposed."""

        if "enable_docs" in self.model_fields_set:
            return self.enable_docs

        environment = self.environment.strip().lower()
        allowed_environments = tuple(env.lower() for env in self.docs_environment_allowlist)
        return environment in allowed_environments

    @property
    def docs_urls(self) -> tuple[str | None, str | None]:
        """Return documentation endpoints honouring the docs visibility rules."""

        if not self.docs_enabled:
            return (None, None)
        return self.docs_url, self.redoc_url

    @property
    def openapi_docs_url(self) -> str | None:
        """Return the OpenAPI endpoint when documentation is enabled."""

        return self.openapi_url if self.docs_enabled else None

    @property
    def sso_enabled(self) -> bool:
        """Return ``True`` when all mandatory SSO settings are present."""

        return all(
            (
                self.sso_client_id,
                self.sso_client_secret,
                self.sso_issuer,
                self.sso_redirect_url,
            )
        )

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

    @field_validator("sso_scope", mode="before")
    @classmethod
    def _normalise_scope(cls, value: str) -> str:
        scopes = " ".join(part for part in value.split() if part)
        if not scopes:
            raise ValueError("sso_scope must not be empty")
        return scopes

    @model_validator(mode="after")
    def _finalise(self) -> Settings:
        self.data_dir = Path(self.data_dir).resolve()
        documents_dir = self.documents_dir or self.data_dir / "documents"
        self.documents_dir = Path(documents_dir).resolve()
        return self


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
