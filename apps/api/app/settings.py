"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

import base64
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---- Defaults ---------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]
DEFAULT_DATA_DIR = Path("./data")            # resolve later
DEFAULT_DB_FILENAME = "ade.sqlite"

DEFAULT_SUBDIRS = {
    "documents_dir": "documents",
    "configs_dir": "config_packages",
    "venvs_dir": "venvs",
    "jobs_dir": "jobs",
    "pip_cache_dir": "cache/pip",
}

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


# ---- Helpers ----------------------------------------------------------------

def _parse_duration(value: Any, *, field_name: str) -> timedelta:
    """Accept seconds (int/float/str) or '60s'/'5m'/'1h'/'14d'."""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError(f"{field_name} must not be blank")
        try:
            seconds = float(s)  # plain seconds
        except ValueError:
            unit = s[-1].lower()
            num = s[:-1].strip()
            if unit not in _UNIT_SECONDS or not num:
                raise ValueError(f"{field_name} must be secs or 'Xs','Xm','Xh','Xd'")
            seconds = float(num) * _UNIT_SECONDS[unit]
    else:
        raise TypeError(f"{field_name} must be number, duration string, or timedelta")
    if seconds <= 0:
        raise ValueError(f"{field_name} must be > 0 seconds")
    return timedelta(seconds=seconds)


def _list_from_env(value: Any, *, default: list[str]) -> list[str]:
    """JSON array or comma string; strip empties; dedupe preserving order."""
    if value in (None, "", []):
        items = list(default)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            items = list(default)
        elif s.startswith("["):
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError as exc:
                raise ValueError("Expected a JSON array") from exc
            if not isinstance(parsed, list):
                raise ValueError("Expected a JSON array")
            items = [str(x).strip() for x in parsed if str(x).strip()]
        else:
            items = [seg.strip() for seg in s.split(",") if seg.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(x).strip() for x in value if str(x).strip()]
    else:
        raise TypeError("Expected string or list")

    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _resolve_dir(base: Path, override: Path | None, default_subdir: str) -> Path:
    """
    If override is None -> <base>/<default_subdir>.
    If override is absolute -> use as-is.
    If override is relative -> <base>/<override>.
    Return absolute, resolved path.
    """
    p = (base / default_subdir) if override is None else override.expanduser()
    if not p.is_absolute():
        p = base / p
    return p.resolve()


# ---- Settings ---------------------------------------------------------------

class Settings(BaseSettings):
    """FastAPI settings loaded from ADE_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    debug: bool = False
    dev_mode: bool = False
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "0.1.0"
    api_docs_enabled: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    logging_level: str = "INFO"
    safe_mode: bool = False

    # Server
    server_host: str = "localhost"
    server_port: int = Field(8000, ge=1, le=65535)
    server_public_url: str = DEFAULT_PUBLIC_URL
    server_cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    # Storage
    data_dir: Path = DEFAULT_DATA_DIR
    documents_dir: Path | None = None
    configs_dir: Path | None = None
    venvs_dir: Path | None = None
    jobs_dir: Path | None = None
    pip_cache_dir: Path | None = None
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    secret_key: SecretStr = Field(default=SecretStr("ZGV2ZWxvcG1lbnQtY29uZmlnLXNlY3JldC1rZXktMzI="))  # base64-encoded 32 bytes

    # Database
    database_dsn: str | None = None
    database_echo: bool = False
    database_pool_size: int = Field(5, ge=1)       # ignored by sqlite; relevant for Postgres
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)

    # JWT
    jwt_secret: SecretStr = Field(default=SecretStr("development-secret"))
    jwt_algorithm: str = "HS256"
    jwt_access_ttl: timedelta = Field(default=timedelta(hours=1))
    jwt_refresh_ttl: timedelta = Field(default=timedelta(days=14))

    # Sessions
    session_cookie_name: str = "ade_session"
    session_refresh_cookie_name: str = "ade_refresh"
    session_csrf_cookie_name: str = "ade_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_last_seen_interval: timedelta = Field(default=timedelta(minutes=5))

    # Auth policy
    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))

    # Jobs & workers
    max_concurrency: int | None = Field(default=None, ge=1)
    queue_size: int | None = Field(default=None, ge=1)
    job_timeout_seconds: int | None = Field(default=None, ge=1)  # accepts '5m', '300'
    worker_cpu_seconds: int | None = Field(default=None, ge=1)   # plain seconds
    worker_mem_mb: int | None = Field(default=None, ge=1)
    worker_fsize_mb: int | None = Field(default=None, ge=1)

    # OIDC
    oidc_enabled: bool = False
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_issuer: str | None = None
    oidc_redirect_url: str | None = None  # may be relative ('/auth/callback')
    oidc_scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    auth_force_sso: bool = False
    auth_sso_auto_provision: bool = True

    # ---- Validators ----

    @field_validator("server_host", mode="before")
    @classmethod
    def _v_host(cls, v: Any) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("ADE_SERVER_HOST must not be empty")
        return s

    @field_validator("server_public_url", mode="before")
    @classmethod
    def _v_public_url(cls, v: Any) -> str:
        s = str(v).strip()
        p = urlparse(s)
        if p.scheme not in {"http", "https"} or not p.netloc:
            raise ValueError("ADE_SERVER_PUBLIC_URL must be an http(s) URL")
        return s.rstrip("/")

    @field_validator("logging_level", mode="before")
    @classmethod
    def _v_log_level(cls, v: Any) -> str:
        s = ("" if v is None else str(v).strip()).upper()
        return s or "INFO"

    @field_validator("server_cors_origins", mode="before")
    @classmethod
    def _v_cors(cls, v: Any) -> list[str]:
        return _list_from_env(v, default=DEFAULT_CORS_ORIGINS)

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def _v_scopes(cls, v: Any) -> list[str]:
        return _list_from_env(v, default=["openid", "email", "profile"])

    @field_validator(
        "jwt_access_ttl",
        "jwt_refresh_ttl",
        "session_last_seen_interval",
        "failed_login_lock_duration",
        "storage_document_retention_period",
        mode="before",
    )
    @classmethod
    def _v_durations(cls, v: Any, info: ValidationInfo) -> timedelta:
        return _parse_duration(v, field_name=info.field_name)

    @field_validator("job_timeout_seconds", mode="before")
    @classmethod
    def _v_job_timeout(cls, v: Any) -> int | None:
        if v in (None, ""):
            return None
        return int(_parse_duration(v, field_name="job_timeout_seconds").total_seconds())

    @field_validator("secret_key", mode="before")
    @classmethod
    def _v_secret_key(cls, v: Any) -> SecretStr:
        if v is None:
            raise ValueError("ADE_SECRET_KEY must be provided")
        raw = v.get_secret_value() if isinstance(v, SecretStr) else str(v).strip()
        try:
            decoded = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError("ADE_SECRET_KEY must be base64 encoded") from exc
        if len(decoded) != 32:
            raise ValueError("ADE_SECRET_KEY must decode to exactly 32 bytes")
        return SecretStr(raw)

    @field_validator("oidc_issuer", mode="before")
    @classmethod
    def _v_oidc_issuer(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        s = str(v).strip()
        p = urlparse(s)
        if p.scheme != "https" or not p.netloc:
            raise ValueError("ADE_OIDC_ISSUER must be an https URL")
        return p.geturl().rstrip("/")

    @field_validator("oidc_redirect_url", mode="before")
    @classmethod
    def _v_oidc_redirect(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        s = str(v).strip()
        if s.startswith("/"):
            return s
        p = urlparse(s)
        if p.scheme != "https" or not p.netloc:
            raise ValueError("ADE_OIDC_REDIRECT_URL must be https or a path starting with '/'")
        return p.geturl().rstrip("/")

    # ---- Finalize: resolve paths & validate OIDC ----

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        base = self.data_dir.expanduser().resolve()
        self.data_dir = base

        for attr, subdir in DEFAULT_SUBDIRS.items():
            override = getattr(self, attr)
            setattr(self, attr, _resolve_dir(base, override, subdir))

        if not self.database_dsn:
            sqlite = (base / "db" / DEFAULT_DB_FILENAME).resolve()
            self.database_dsn = f"sqlite+aiosqlite:///{sqlite.as_posix()}"

        if self.oidc_enabled:
            missing = [
                name for name, val in {
                    "ADE_OIDC_CLIENT_ID": self.oidc_client_id,
                    "ADE_OIDC_CLIENT_SECRET": self.oidc_client_secret,
                    "ADE_OIDC_ISSUER": self.oidc_issuer,
                    "ADE_OIDC_REDIRECT_URL": self.oidc_redirect_url,
                }.items() if not val
            ]
            if missing:
                raise ValueError("OIDC enabled but missing: " + ", ".join(missing))
            if "openid" not in self.oidc_scopes:
                self.oidc_scopes = ["openid", *self.oidc_scopes]
            if self.oidc_redirect_url and self.oidc_redirect_url.startswith("/"):
                self.oidc_redirect_url = f"{self.server_public_url}{self.oidc_redirect_url}"
        else:
            # If disabled, discourage partial config that hints at a misconfigured env
            provided = any([
                self.oidc_client_id, self.oidc_client_secret,
                self.oidc_issuer, self.oidc_redirect_url,
            ])
            if provided:
                raise ValueError("Set ADE_OIDC_ENABLED=true when supplying other OIDC settings")

        return self

    # ---- Convenience ----

    @property
    def jwt_secret_value(self) -> str:
        return self.jwt_secret.get_secret_value()

    @property
    def secret_key_bytes(self) -> bytes:
        return base64.b64decode(self.secret_key.get_secret_value(), validate=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


__all__ = [
    "PROJECT_ROOT",
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_DATA_DIR",
    "DEFAULT_DB_FILENAME",
    "DEFAULT_PUBLIC_URL",
    "DEFAULT_SUBDIRS",
    "Settings",
    "get_settings",
    "reload_settings",
]
