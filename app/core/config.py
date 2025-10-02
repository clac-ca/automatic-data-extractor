"""Configuration models for the ADE application."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from datetime import timedelta
from pathlib import Path
from typing import Any
from collections.abc import MutableMapping

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "var"
DEFAULT_DOCUMENTS_SUBDIR = "documents"
DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://localhost:8000")

_DURATION_PATTERN = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>[a-zA-Z]+))?$",
    re.IGNORECASE,
)
_DURATION_UNITS = {
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


def _resolve_path(value: Any, *, fallback: Path) -> Path:
    if value in (None, "", False):
        target = fallback
    else:
        target = value if isinstance(value, Path) else Path(str(value))
    return target.expanduser().resolve()


def _parse_duration(raw_value: Any, *, field_name: str) -> timedelta:
    if isinstance(raw_value, timedelta):
        return raw_value
    if raw_value is None:
        raise ValueError(f"{field_name} may not be null")

    if isinstance(raw_value, (int, float)):
        seconds = float(raw_value)
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            raise ValueError(f"{field_name} must not be blank")
        match = _DURATION_PATTERN.match(text)
        if not match:
            raise ValueError(
                f"{field_name} must be numeric seconds or a value like '15m', '1h', or '30 minutes'",
            )
        number = float(match.group("value"))
        unit = match.group("unit")
        if unit:
            multiplier = _DURATION_UNITS.get(unit.lower())
            if multiplier is None:
                raise ValueError(
                    f"Unsupported duration unit for {field_name}. Use seconds (s), minutes (m), hours (h), or days (d).",
                )
            seconds = number * multiplier
        else:
            seconds = number
    else:
        raise TypeError(f"{field_name} must be provided as a number or string")

    if seconds <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return timedelta(seconds=seconds)


def _parse_cors_origins(raw_value: Any) -> list[str]:
    if raw_value is None or raw_value == "":
        return []
    if isinstance(raw_value, str):
        payload = raw_value.strip()
        if not payload:
            return []
        if payload.startswith("["):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "server_cors_origins must be a JSON array or comma separated list",
                ) from exc
            raw_value = parsed
        else:
            return [segment.strip() for segment in re.split(r"[\s,]+", payload) if segment.strip()]
    if isinstance(raw_value, (list, tuple, set)):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    raise TypeError("server_cors_origins must be provided as a string or list of origins")


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value().strip())
    if isinstance(value, str):
        return bool(value.strip())
    return True


class Settings(BaseSettings):
    """FastAPI configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
    )

    @staticmethod
    def _normalise_env_list(
        env_vars: MutableMapping[str, str],
        *,
        key: str,
        split_pattern: str,
    ) -> None:
        raw = env_vars.get(key)
        if raw is None:
            return
        payload = raw.strip()
        if not payload:
            env_vars[key] = "[]"
            return
        if payload.startswith("["):
            return
        items = [segment.strip() for segment in re.split(split_pattern, payload) if segment.strip()]
        env_vars[key] = json.dumps(items) if items else "[]"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        for source in (env_settings, dotenv_settings):
            env_vars = getattr(source, "env_vars", None)
            if isinstance(env_vars, MutableMapping):
                cls._normalise_env_list(
                    env_vars,
                    key="ADE_SERVER_CORS_ORIGINS",
                    split_pattern=r"[\s,]+",
                )
                cls._normalise_env_list(
                    env_vars,
                    key="ade_server_cors_origins",
                    split_pattern=r"[\s,]+",
                )
                cls._normalise_env_list(
                    env_vars,
                    key="ADE_OIDC_SCOPES",
                    split_pattern=r"[\s,]+",
                )
                cls._normalise_env_list(
                    env_vars,
                    key="ade_oidc_scopes",
                    split_pattern=r"[\s,]+",
                )
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    debug: bool = Field(False, description="Enable FastAPI debug mode.")
    dev_mode: bool = Field(False, description="Enable developer conveniences like auto-reload.")
    app_name: str = Field("Automatic Data Extractor API", description="Human readable API name.")
    app_version: str = Field("0.1.0", description="API version string exposed in docs.")
    api_docs_enabled: bool = Field(False, description="Expose interactive API documentation routes.")
    docs_url: str = Field("/docs", description="Swagger UI mount point.")
    redoc_url: str = Field("/redoc", description="ReDoc mount point.")
    openapi_url: str = Field("/openapi.json", description="OpenAPI schema path.")
    logging_level: str = Field("INFO", description="Root logging level for the backend application.")

    server_host: str = Field("localhost", description="Network interface the server binds to.")
    server_port: int = Field(8000, ge=1, le=65535, description="Port that uvicorn listens on.")
    server_public_url: str = Field(
        DEFAULT_PUBLIC_URL,
        description="Public origin (scheme + host + optional port) used by clients.",
    )
    server_cors_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        description="Allowed CORS origins. Provide a comma separated list in the environment.",
    )

    storage_data_dir: Path = Field(
        DEFAULT_DATA_DIR,
        description="Writable directory for databases, caches, and derived artefacts.",
    )
    storage_documents_dir: Path | None = Field(
        None,
        description="Directory for uploaded documents. Defaults to <storage_data_dir>/documents.",
    )

    database_dsn: str = Field(
        "sqlite+aiosqlite:///./var/db/ade.sqlite",
        description="SQLAlchemy database connection string.",
    )
    database_echo: bool = Field(False, description="Enable SQLAlchemy engine echo logging.")
    database_pool_size: int = Field(5, ge=1, description="SQLAlchemy connection pool size.")
    database_max_overflow: int = Field(10, ge=0, description="SQLAlchemy connection pool overflow size.")
    database_pool_timeout: int = Field(30, gt=0, description="SQLAlchemy pool timeout in seconds.")

    jwt_secret: SecretStr = Field(
        SecretStr("development-secret"),
        description="Secret used to sign JWTs.",
    )
    jwt_algorithm: str = Field("HS256", description="JWT signing algorithm.")
    jwt_access_ttl: timedelta = Field(
        timedelta(minutes=60),
        description="Access token lifetime. Accepts seconds or suffixed values like '15m'.",
    )
    jwt_refresh_ttl: timedelta = Field(
        timedelta(days=14),
        description="Refresh token lifetime. Accepts seconds or suffixed values like '7d'.",
    )

    session_cookie_name: str = Field("ade_session", description="Session cookie name.")
    session_refresh_cookie_name: str = Field("ade_refresh", description="Refresh cookie name.")
    session_csrf_cookie_name: str = Field("ade_csrf", description="CSRF cookie name.")
    session_cookie_domain: str | None = Field(
        None,
        description="Optional domain attribute applied to authentication cookies.",
    )
    session_cookie_path: str = Field("/", description="Cookie path scope.")

    oidc_enabled: bool = Field(False, description="Enable OpenID Connect login flow when fully configured.")
    oidc_client_id: str | None = Field(None, description="OIDC client identifier.")
    oidc_client_secret: SecretStr | None = Field(None, description="OIDC client secret.")
    oidc_issuer: str | None = Field(None, description="OIDC issuer URL.")
    oidc_redirect_url: str | None = Field(None, description="OIDC redirect callback URL.")
    oidc_scopes: list[str] = Field(
        default_factory=lambda: ["openid", "email", "profile"],
        description="Scopes requested during the OIDC authorisation flow.",
    )
    oidc_resource_audience: str | None = Field(
        None,
        description="Optional audience parameter requested from the identity provider.",
    )

    session_last_seen_interval: timedelta = Field(
        timedelta(seconds=300),
        description="Minimum interval between API key last-seen updates.",
    )
    storage_upload_max_bytes: int = Field(
        25 * 1024 * 1024,
        gt=0,
        description="Maximum upload size in bytes.",
    )
    storage_document_retention_period: timedelta = Field(
        timedelta(days=30),
        description="Default document retention window. Accepts seconds or suffixed values like '30d'.",
    )

    @field_validator("server_host", mode="before")
    @classmethod
    def _clean_host(cls, value: Any) -> Any:
        if value is None:
            return value
        host = str(value).strip()
        if not host:
            raise ValueError("server_host must not be empty")
        return host

    @field_validator("server_public_url", mode="before")
    @classmethod
    def _clean_public_url(cls, value: Any) -> str:
        if value is None:
            raise ValueError("server_public_url must not be empty")
        url = str(value).strip()
        if not url:
            raise ValueError("server_public_url must not be empty")
        return url

    @field_validator("server_cors_origins", mode="before")
    @classmethod
    def _prepare_cors(cls, value: Any) -> list[str]:
        return _parse_cors_origins(value)

    @field_validator("storage_data_dir", mode="before")
    @classmethod
    def _prepare_data_dir(cls, value: Any) -> Path:
        return _resolve_path(value, fallback=DEFAULT_DATA_DIR)

    @field_validator("session_cookie_name", "session_refresh_cookie_name", "session_csrf_cookie_name", mode="before")
    @classmethod
    def _clean_cookie_name(cls, value: Any) -> str:
        if value is None:
            raise ValueError("Cookie names must not be empty")
        name = str(value).strip()
        if not name:
            raise ValueError("Cookie names must not be empty")
        if any(char.isspace() for char in name):
            raise ValueError("Cookie names must not contain whitespace")
        return name

    @field_validator("session_cookie_domain", "oidc_resource_audience", "oidc_client_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("session_cookie_path", mode="before")
    @classmethod
    def _clean_cookie_path(cls, value: Any) -> str:
        if value is None:
            return "/"
        path = str(value).strip()
        if not path:
            raise ValueError("session_cookie_path must not be empty")
        if not path.startswith("/"):
            raise ValueError("session_cookie_path must start with '/'")
        return path

    @field_validator("oidc_client_secret", mode="before")
    @classmethod
    def _prepare_secret(cls, value: Any) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        secret = secret.strip()
        if not secret:
            return None
        return SecretStr(secret)

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def _prepare_scopes(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "oidc_scopes must be a JSON array or comma separated string",
                    ) from exc
                value = parsed
            else:
                scopes = [segment.strip() for segment in re.split(r"[\s,]+", text) if segment.strip()]
                if not scopes:
                    raise ValueError("oidc_scopes must not be empty")
                return sorted(set(scopes))
        if isinstance(value, (list, tuple, set)):
            scopes = {str(item).strip() for item in value if str(item).strip()}
            if not scopes:
                raise ValueError("oidc_scopes must not be empty")
            return sorted(scopes)
        raise TypeError("oidc_scopes must be provided as a string or list of strings")

    @field_validator(
        "jwt_access_ttl",
        "jwt_refresh_ttl",
        "session_last_seen_interval",
        "storage_document_retention_period",
        mode="before",
    )
    @classmethod
    def _coerce_durations(cls, value: Any, info: Any) -> timedelta:
        return _parse_duration(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _finalise(self) -> "Settings":
        data_dir = _resolve_path(self.storage_data_dir, fallback=DEFAULT_DATA_DIR)
        self.storage_data_dir = data_dir

        documents_default = data_dir / DEFAULT_DOCUMENTS_SUBDIR
        documents_source = self.storage_documents_dir or documents_default
        self.storage_documents_dir = _resolve_path(documents_source, fallback=documents_default)

        unique_origins: list[str] = []
        seen: set[str] = set()
        for origin in [*self.server_cors_origins, self.server_public_url]:
            cleaned = origin.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            unique_origins.append(cleaned)
        self.server_cors_origins = unique_origins

        required = {
            "oidc_client_id": self.oidc_client_id,
            "oidc_client_secret": self.oidc_client_secret,
            "oidc_issuer": self.oidc_issuer,
            "oidc_redirect_url": self.oidc_redirect_url,
        }
        provided = {key: value for key, value in required.items() if _value_present(value)}
        if self.oidc_enabled and len(provided) != len(required):
            missing = sorted(set(required) - set(provided))
            raise ValueError(
                "oidc_enabled is true but required OIDC settings are missing: "
                + ", ".join(missing)
            )
        if not self.oidc_enabled and provided and len(provided) != len(required):
            missing = sorted(set(required) - set(provided))
            raise ValueError(
                "OIDC configuration incomplete. Provide all of: " + ", ".join(missing)
            )
        self.oidc_enabled = len(provided) == len(required)

        return self

    @property
    def jwt_secret_value(self) -> str:
        return self.jwt_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings loaded from the environment."""

    return Settings()  # pyright: ignore[reportCallIssue]


def reload_settings() -> Settings:
    """Reload settings from the environment and refresh the cache."""

    get_settings.cache_clear()
    return get_settings()


__all__ = [
    "DEFAULT_DATA_DIR",
    "DEFAULT_DOCUMENTS_SUBDIR",
    "DEFAULT_PUBLIC_URL",
    "PROJECT_ROOT",
    "Settings",
    "get_settings",
    "reload_settings",
]
