"""Application configuration for the ADE backend."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import MutableMapping
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Request

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Paths & defaults
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = (PROJECT_ROOT / "data").resolve()
DEFAULT_DOCUMENTS_SUBDIR = "documents"
DEFAULT_CONFIGS_SUBDIR = "configs"
DEFAULT_DATABASE_SUBDIR = "db"
DEFAULT_DATABASE_FILENAME = "backend.app.sqlite"
DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = (DEFAULT_PUBLIC_URL,)
DEFAULT_DEV_FRONTEND_ORIGINS = ("http://localhost:5173",)

_DURATION_PATTERN = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>[a-zA-Z]+))?$", re.IGNORECASE)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_duration(value: Any, *, field_name: str) -> timedelta:
    if isinstance(value, timedelta):
        return value
    if value is None:
        raise ValueError(f"{field_name} may not be null")
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        text = value.strip()
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


def _normalise_path(value: Path, *, base: Path) -> Path:
    expanded = value.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (base / expanded).resolve()


def _load_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Expected JSON array") from exc
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array")
    return list(parsed)


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """FastAPI configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        def _prepare_env_list(source, key: str) -> None:
            env_vars = getattr(source, "env_vars", None)
            if not isinstance(env_vars, MutableMapping):
                return
            for variant in (key, key.lower()):
                raw = env_vars.get(variant)
                if raw is None:
                    continue
                payload = str(raw).strip()
                if not payload:
                    env_vars[variant] = "[]"
                    continue
                if payload.startswith("["):
                    continue
                items = [segment.strip() for segment in payload.split(",") if segment.strip()]
                env_vars[variant] = json.dumps(items) if items else "[]"

        for source in (env_settings, dotenv_settings):
            _prepare_env_list(source, "ADE_SERVER_CORS_ORIGINS")
            _prepare_env_list(source, "ADE_OIDC_SCOPES")

        return init_settings, env_settings, dotenv_settings, file_secret_settings

    # General application settings ------------------------------------------------
    debug: bool = False
    dev_mode: bool = False
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "0.1.0"
    api_docs_enabled: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    logging_level: str = "INFO"

    # Server ---------------------------------------------------------------------
    server_host: str = "localhost"
    server_port: int = Field(8000, ge=1, le=65535)
    server_public_url: str = DEFAULT_PUBLIC_URL
    server_cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    # Storage --------------------------------------------------------------------
    storage_data_dir: Path = Field(default=DEFAULT_DATA_DIR)
    storage_documents_dir: Path | None = None
    storage_configs_dir: Path | None = None
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    secret_key: SecretStr = Field(
        default=SecretStr("ZGV2ZWxvcG1lbnQtY29uZmlnLXNlY3JldC1rZXktMzI=")
    )

    # Database -------------------------------------------------------------------
    database_dsn: str | None = None
    database_echo: bool = False
    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)

    # JWT ------------------------------------------------------------------------
    jwt_secret: SecretStr = Field(default=SecretStr("development-secret"))
    jwt_algorithm: str = "HS256"
    jwt_access_ttl: timedelta = Field(default=timedelta(hours=1))
    jwt_refresh_ttl: timedelta = Field(default=timedelta(days=14))

    # Sessions -------------------------------------------------------------------
    session_cookie_name: str = "backend_app_session"
    session_refresh_cookie_name: str = "backend_app_refresh"
    session_csrf_cookie_name: str = "backend_app_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_last_seen_interval: timedelta = Field(default=timedelta(minutes=5))

    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))

    # OIDC -----------------------------------------------------------------------
    oidc_enabled: bool = False
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_issuer: str | None = None
    oidc_redirect_url: str | None = None
    oidc_scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    # Authentication -------------------------------------------------------------
    auth_force_sso: bool = False
    auth_sso_auto_provision: bool = True
    safe_mode: bool = False

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("server_host", mode="before")
    @classmethod
    def _clean_host(cls, value: Any) -> str:
        if value is None:
            raise ValueError("server_host must not be empty")
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
    def _parse_cors(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return list(DEFAULT_CORS_ORIGINS)
        if isinstance(value, str):
            payload = value.strip()
            if not payload:
                return []
            if payload.startswith("["):
                items = _load_json_list(payload)
            else:
                items = [segment.strip() for segment in payload.split(",")]
            return [item for item in (str(entry).strip() for entry in items) if item]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("server_cors_origins must be a string or list")

    @field_validator("storage_data_dir", mode="before")
    @classmethod
    def _coerce_data_dir(cls, value: Any) -> Path:
        if value in (None, ""):
            return DEFAULT_DATA_DIR
        if isinstance(value, Path):
            return value
        return Path(str(value).strip())

    @field_validator("storage_documents_dir", mode="before")
    @classmethod
    def _coerce_documents_dir(cls, value: Any) -> Path | None:
        if value in (None, ""):
            return None
        if isinstance(value, Path):
            return value
        return Path(str(value).strip())

    @field_validator("storage_configs_dir", mode="before")
    @classmethod
    def _coerce_configs_dir(cls, value: Any) -> Path | None:
        if value in (None, ""):
            return None
        if isinstance(value, Path):
            return value
        return Path(str(value).strip())

    @field_validator("database_dsn", mode="before")
    @classmethod
    def _clean_database_dsn(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip()

    @field_validator(
        "jwt_access_ttl",
        "jwt_refresh_ttl",
        "session_last_seen_interval",
        "failed_login_lock_duration",
        "storage_document_retention_period",
        mode="before",
    )
    @classmethod
    def _coerce_durations(cls, value: Any, info: ValidationInfo) -> timedelta:
        return _parse_duration(value, field_name=info.field_name)

    @field_validator(
        "session_cookie_name",
        "session_refresh_cookie_name",
        "session_csrf_cookie_name",
        mode="before",
    )
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

    @field_validator("session_cookie_domain", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("oidc_client_id", mode="before")
    @classmethod
    def _trim_optional(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

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

    @field_validator("secret_key", mode="before")
    @classmethod
    def _validate_secret_key(cls, value: Any) -> SecretStr:
        if value is None:
            raise ValueError("secret_key must be provided")
        secret = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        secret = secret.strip()
        if not secret:
            raise ValueError("secret_key must not be blank")
        try:
            decoded = base64.b64decode(secret, validate=True)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("secret_key must be base64 encoded") from exc
        if len(decoded) != 32:
            raise ValueError("secret_key must decode to exactly 32 bytes")
        return SecretStr(secret)

    @field_validator("oidc_issuer", mode="before")
    @classmethod
    def _validate_oidc_issuer(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        candidate = str(value).strip()
        if not candidate:
            return None
        parsed = urlparse(candidate)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("oidc_issuer must be an https URL")
        normalised = parsed._replace(path=parsed.path.rstrip("/"))
        return normalised.geturl().rstrip("/")

    @field_validator("oidc_redirect_url", mode="before")
    @classmethod
    def _validate_oidc_redirect(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        candidate = str(value).strip()
        if not candidate:
            return None
        if candidate.startswith("/"):
            return candidate
        parsed = urlparse(candidate)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("oidc_redirect_url must be an https URL or an absolute path")
        return parsed.geturl()

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def _prepare_scopes(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return ["openid", "email", "profile"]
        if isinstance(value, str):
            payload = value.strip()
            if not payload:
                return ["openid", "email", "profile"]
            if payload.startswith("["):
                items = _load_json_list(payload)
            else:
                items = [segment.strip() for segment in payload.split(",")]
        elif isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value]
        else:
            raise TypeError("oidc_scopes must be provided as a string or list")
        scopes = sorted({item for item in items if item})
        if not scopes:
            raise ValueError("oidc_scopes must not be empty")
        return scopes


    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _finalise(self) -> "Settings":
        data_dir = _normalise_path(self.storage_data_dir, base=PROJECT_ROOT)
        self.storage_data_dir = data_dir

        documents_dir = self.storage_documents_dir
        if documents_dir is None:
            documents_dir = data_dir / DEFAULT_DOCUMENTS_SUBDIR
        documents_dir = _normalise_path(documents_dir, base=data_dir)
        self.storage_documents_dir = documents_dir

        configs_dir = self.storage_configs_dir
        if configs_dir is None:
            configs_dir = data_dir / DEFAULT_CONFIGS_SUBDIR
        configs_dir = _normalise_path(configs_dir, base=data_dir)
        self.storage_configs_dir = configs_dir

        if not self.database_dsn:
            sqlite_path = (data_dir / DEFAULT_DATABASE_SUBDIR / DEFAULT_DATABASE_FILENAME).resolve()
            self.database_dsn = f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"

        origins: list[str] = []
        seen: set[str] = set()
        for origin in [*self.server_cors_origins, self.server_public_url]:
            cleaned = origin.strip()
            if cleaned and cleaned not in seen:
                origins.append(cleaned)
                seen.add(cleaned)
        if (
            "server_cors_origins" not in self.model_fields_set
            and DEFAULT_PUBLIC_URL in seen
            and self.server_public_url != DEFAULT_PUBLIC_URL
        ):
            origins = [origin for origin in origins if origin != DEFAULT_PUBLIC_URL]
        if self.server_public_url != DEFAULT_PUBLIC_URL:
            dev_defaults = set(DEFAULT_DEV_FRONTEND_ORIGINS) | {DEFAULT_PUBLIC_URL}
            if all(origin == self.server_public_url or origin in dev_defaults for origin in origins):
                origins = [origin for origin in origins if origin == self.server_public_url]
        self.server_cors_origins = origins

        redirect = self.oidc_redirect_url or ""
        if redirect.startswith("/"):
            base_origin = self.server_public_url.rstrip("/")
            if not base_origin:
                raise ValueError("server_public_url must be configured when using relative oidc_redirect_url")
            self.oidc_redirect_url = f"{base_origin}{redirect}"

        required = {
            "oidc_client_id": self.oidc_client_id,
            "oidc_client_secret": self.oidc_client_secret,
            "oidc_issuer": self.oidc_issuer,
            "oidc_redirect_url": self.oidc_redirect_url,
        }
        provided = {key: value for key, value in required.items() if value}

        if self.oidc_enabled and len(provided) != len(required):
            missing = sorted(set(required) - set(provided))
            raise ValueError(
                "oidc_enabled is true but required OIDC settings are missing: " + ", ".join(missing),
            )
        if not self.oidc_enabled and provided and len(provided) != len(required):
            missing = sorted(set(required) - set(provided))
            raise ValueError("OIDC configuration incomplete. Provide all of: " + ", ".join(missing))
        self.oidc_enabled = len(provided) == len(required)

        return self

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def jwt_secret_value(self) -> str:
        return self.jwt_secret.get_secret_value()

    @property
    def secret_key_bytes(self) -> bytes:
        encoded = self.secret_key.get_secret_value()
        return base64.b64decode(encoded, validate=True)

    @property
    def safe_mode_enabled(self) -> bool:
        return bool(self.safe_mode)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings loaded from the environment."""

    return Settings()  # pyright: ignore[reportCallIssue]


def reload_settings() -> Settings:
    """Reload settings from the environment and refresh the cache."""

    get_settings.cache_clear()
    return get_settings()


def get_app_settings(request: Request) -> Settings:
    """Return the application settings cached on the FastAPI app."""

    state = getattr(request.app, "state", None)
    settings = getattr(state, "settings", None)
    if isinstance(settings, Settings):
        return settings

    refreshed = get_settings()
    if state is not None:
        state.settings = refreshed
    return refreshed


__all__ = [
    "DEFAULT_DATA_DIR",
    "DEFAULT_DATABASE_FILENAME",
    "DEFAULT_DATABASE_SUBDIR",
    "DEFAULT_CONFIGS_SUBDIR",
    "DEFAULT_PUBLIC_URL",
    "PROJECT_ROOT",
    "Settings",
    "get_app_settings",
    "get_settings",
    "reload_settings",
]
