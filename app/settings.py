"""Application settings for the ADE FastAPI backend."""

from __future__ import annotations

import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, cast, runtime_checkable

from pydantic import (
    AnyHttpUrl,
    DirectoryPath,
    Field,
    SecretStr,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "var"
DEFAULT_DOCUMENTS_DIR = DEFAULT_DATA_DIR / "documents"
DEFAULT_PUBLIC_URL: AnyHttpUrl = TypeAdapter(AnyHttpUrl).validate_python(
    "http://localhost:8000"
)

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]


class Settings(BaseSettings):
    """FastAPI configuration loaded from environment variables."""

    model_config: ClassVar[SettingsConfigDict] = cast(
        SettingsConfigDict,
        {
            "env_file": ".env",
            "env_prefix": "ADE_",
            "case_sensitive": False,
            "extra": "ignore",
            "parse_env_var": "_parse_env_var",
        },
    )

    _DURATION_UNITS: ClassVar[dict[str, int]] = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }
    _DURATION_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>[a-zA-Z]+))?$",
        re.IGNORECASE,
    )

    debug: bool = Field(default=False, description="Enable FastAPI debug mode.")
    dev_mode: bool = Field(
        default=False,
        description="Enable developer-focused behaviours (hot reloading, verbose errors).",
    )
    app_name: str = Field(
        default="Automatic Data Extractor API",
        description="Human readable API name.",
    )
    app_version: str = Field(default="0.1.0", description="API version string.")
    api_docs_enabled: bool = Field(
        default=False,
        description="Expose interactive API documentation endpoints.",
    )
    docs_url: str = Field(default="/docs", description="Swagger UI mount point.")
    redoc_url: str = Field(default="/redoc", description="ReDoc mount point.")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI schema endpoint.")
    logging_level: LogLevel = Field(
        default="INFO",
        description="Root log level for the backend application.",
    )

    server_host: str = Field(
        default="localhost",
        description="Network interface for the uvicorn server to bind.",
    )
    server_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port that the uvicorn server listens on.",
    )
    server_public_url: AnyHttpUrl = Field(
        default=DEFAULT_PUBLIC_URL,
        description="Public origin clients use to reach the backend (scheme + host + optional port).",
    )
    server_cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        description="Additional allowed CORS origins (comma/whitespace list or JSON array).",
    )

    storage_data_dir: DirectoryPath = Field(
        default=DEFAULT_DATA_DIR,
        validate_default=True,
        description="Directory for writable backend data (database, caches, generated artefacts).",
    )
    storage_documents_dir: DirectoryPath = Field(
        default=DEFAULT_DOCUMENTS_DIR,
        validate_default=True,
        description="Directory for uploaded documents and derived files.",
    )

    database_dsn: str = Field(
        default="sqlite+aiosqlite:///./var/db/ade.sqlite",
        description="SQLAlchemy database URL.",
    )
    database_echo: bool = Field(
        default=False,
        description="Enable SQLAlchemy engine echo logging.",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        description="SQLAlchemy connection pool size.",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        description="SQLAlchemy connection pool overflow.",
    )
    database_pool_timeout: int = Field(
        default=30,
        gt=0,
        description="SQLAlchemy pool timeout in seconds.",
    )

    jwt_secret: SecretStr = Field(
        default=SecretStr("development-secret"),
        description="HMAC secret for JWT tokens.",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm used for JWT signing.",
    )
    jwt_access_ttl: timedelta = Field(
        default=timedelta(minutes=60),
        description="Access token lifetime (seconds or suffixed strings like '15m').",
    )
    jwt_refresh_ttl: timedelta = Field(
        default=timedelta(days=14),
        description="Refresh token lifetime (seconds or suffixed strings like '7d').",
    )

    session_cookie_name: str = Field(
        default="ade_session",
        description="Name of the session cookie.",
    )
    session_refresh_cookie_name: str = Field(
        default="ade_refresh",
        description="Name of the refresh cookie.",
    )
    session_csrf_cookie_name: str = Field(
        default="ade_csrf",
        description="Name of the CSRF cookie.",
    )
    session_cookie_domain: str | None = Field(
        default=None,
        description="Optional cookie domain override.",
    )
    session_cookie_path: str = Field(
        default="/",
        description="Cookie path scope.",
    )

    oidc_enabled: bool = Field(
        default=False,
        description="Enable OpenID Connect login flow.",
    )
    oidc_client_id: str | None = Field(
        default=None,
        description="OIDC client identifier.",
    )
    oidc_client_secret: SecretStr | None = Field(
        default=None,
        description="OIDC client secret.",
    )
    oidc_issuer: AnyHttpUrl | None = Field(
        default=None,
        description="OIDC issuer URL.",
    )
    oidc_redirect_url: AnyHttpUrl | None = Field(
        default=None,
        description="OIDC redirect URL.",
    )
    oidc_scopes: list[str] = Field(
        default_factory=lambda: ["openid", "email", "profile"],
        description="OIDC scopes requested.",
    )
    oidc_resource_audience: str | None = Field(
        default=None,
        description="OIDC resource audience.",
    )

    session_last_seen_interval: timedelta = Field(
        default=timedelta(seconds=300),
        description="Minimum interval between API key last-seen updates (seconds or suffixed strings).",
    )
    storage_upload_max_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        description="Maximum upload size in bytes.",
    )
    storage_document_retention_period: timedelta = Field(
        default=timedelta(days=30),
        description="Default document retention period (seconds or suffixed strings like '30d').",
    )

    @classmethod
    def _parse_env_var(cls, field_name: str, raw_value: str) -> Any:
        """Return raw environment values so field validators can normalise them."""

        return raw_value

    @staticmethod
    def _ensure_directory(path_value: Any) -> Path:
        path = Path(path_value).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    @classmethod
    def _parse_timedelta(cls, value: Any) -> timedelta:
        if isinstance(value, timedelta):
            return value
        if value is None:
            raise ValueError("Duration value may not be null")
        seconds: float
        if isinstance(value, (int, float)):
            seconds = float(value)
        elif isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                raise ValueError("Duration value must not be blank")
            match = cls._DURATION_PATTERN.match(candidate)
            if not match:
                raise ValueError(
                    "Duration must be numeric seconds or a value like '15m', '1h', or '30 minutes'",
                )
            number = float(match.group("value"))
            unit = match.group("unit")
            if unit is None:
                seconds = number
            else:
                multiplier = cls._DURATION_UNITS.get(unit.lower())
                if multiplier is None:
                    raise ValueError(
                        "Unsupported duration unit. Use seconds (s), minutes (m), hours (h), or days (d).",
                    )
                seconds = number * multiplier
        else:
            raise TypeError("Duration must be provided as a number or string")

        if seconds <= 0:
            raise ValueError("Duration must be greater than zero")
        return timedelta(seconds=seconds)

    @field_validator("server_host", mode="before")
    @classmethod
    def _normalise_host(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("server_host must not be empty")
        return host

    @field_validator("server_cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, value: Any) -> list[str] | Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "server_cors_origins must be a JSON array or comma separated list",
                    ) from exc
                if not isinstance(parsed, list):
                    raise ValueError("server_cors_origins JSON payload must be a list")
                return [str(item) for item in parsed]
            tokens = [segment.strip() for segment in re.split(r"[\s,]+", raw) if segment.strip()]
            return tokens
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("server_cors_origins must be a string or list of origins")

    @field_validator("session_cookie_domain", "oidc_resource_audience", mode="before")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator(
        "session_cookie_name",
        "session_refresh_cookie_name",
        "session_csrf_cookie_name",
        mode="before",
    )
    @classmethod
    def _normalise_cookie_name(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("Session cookie names must not be empty")
        if any(char.isspace() for char in candidate):
            raise ValueError("Session cookie names must not contain whitespace")
        return candidate

    @field_validator("oidc_client_id", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("session_cookie_path", mode="before")
    @classmethod
    def _normalise_cookie_path(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("session_cookie_path must not be empty")
        if not candidate.startswith("/"):
            raise ValueError("session_cookie_path must start with '/'")
        return candidate

    @field_validator("oidc_client_secret", mode="before")
    @classmethod
    def _normalise_secret(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, SecretStr):
            if not value.get_secret_value().strip():
                return None
            return value
        candidate = str(value).strip()
        return candidate or None

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def _parse_scopes(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            tokens = [
                part.strip()
                for part in re.split(r"[\s,]+", value)
                if part.strip()
            ]
            if not tokens:
                raise ValueError("oidc_scopes must not be empty")
            return sorted(set(tokens))
        if isinstance(value, (list, tuple, set)):
            unique_tokens = {str(item).strip() for item in value if str(item).strip()}
            if not unique_tokens:
                raise ValueError("oidc_scopes must not be empty")
            return sorted(unique_tokens)
        raise TypeError("oidc_scopes must be provided as a string or list of strings")

    @field_validator(
        "jwt_access_ttl",
        "jwt_refresh_ttl",
        "session_last_seen_interval",
        "storage_document_retention_period",
        mode="before",
    )
    @classmethod
    def _coerce_duration(cls, value: Any) -> timedelta:
        return cls._parse_timedelta(value)

    @field_validator("storage_data_dir", mode="before")
    @classmethod
    def _prepare_data_dir(cls, value: Any) -> Path:
        return Settings._ensure_directory(value)

    @field_validator("storage_documents_dir", mode="before")
    @classmethod
    def _prepare_documents_dir(cls, value: Any, info: ValidationInfo) -> Path:
        if value is None or value == "":
            base_dir = info.data.get("storage_data_dir") or DEFAULT_DATA_DIR
            return Settings._ensure_directory(Path(base_dir) / DEFAULT_DOCUMENTS_DIR.name)
        if (
            isinstance(value, Path)
            and value == DEFAULT_DOCUMENTS_DIR
            and os.getenv("ADE_STORAGE_DOCUMENTS_DIR") is None
        ):
            base_dir = info.data.get("storage_data_dir") or DEFAULT_DATA_DIR
            return Settings._ensure_directory(Path(base_dir) / DEFAULT_DOCUMENTS_DIR.name)
        return Settings._ensure_directory(value)

    @model_validator(mode="after")
    def _finalise(self) -> Settings:
        directory_adapter = TypeAdapter(DirectoryPath)
        documents_dir = Settings._ensure_directory(self.storage_documents_dir)
        self.storage_documents_dir = directory_adapter.validate_python(documents_dir)

        adapter = TypeAdapter(list[AnyHttpUrl])
        origins = {str(origin) for origin in self.server_cors_origins}
        origins.add(str(self.server_public_url))
        self.server_cors_origins = adapter.validate_python(sorted(origins))

        oidc_fields = {
            "oidc_client_id": self.oidc_client_id,
            "oidc_client_secret": self.oidc_client_secret,
            "oidc_issuer": self.oidc_issuer,
            "oidc_redirect_url": self.oidc_redirect_url,
        }
        provided = {
            key: value
            for key, value in oidc_fields.items()
            if value and (not isinstance(value, SecretStr) or value.get_secret_value())
        }
        if provided and len(provided) != len(oidc_fields):
            missing = sorted(set(oidc_fields) - set(provided))
            raise ValueError(
                "OIDC configuration incomplete. Provide all of: " + ", ".join(missing)
            )
        if self.oidc_enabled and len(provided) != len(oidc_fields):
            raise ValueError(
                "oidc_enabled is true but required OIDC settings are missing"
            )
        self.oidc_enabled = len(provided) == len(oidc_fields)

        return self

    @property
    def jwt_secret_value(self) -> str:
        """Return the plain JWT secret value."""

        return self.jwt_secret.get_secret_value()


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
