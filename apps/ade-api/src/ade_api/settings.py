"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

import json
import secrets
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import Field, PrivateAttr, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

# ---- Defaults ---------------------------------------------------------------

MODULE_DIR = Path(__file__).resolve().parent


def _detect_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "apps").is_dir():
            return p
        if (p / ".git").is_dir():
            return p
    return Path.cwd()


REPO_ROOT = _detect_repo_root(MODULE_DIR)


def _candidate_api_roots() -> list[Path]:
    """Return candidate directories that may hold alembic.ini + migrations."""

    candidates = [
        MODULE_DIR.parent.parent,  # source layout: apps/ade-api
        MODULE_DIR,  # packaged assets alongside the module (if bundled)
        MODULE_DIR.parent,  # site-packages/ade_api
        Path.cwd() / "apps" / "ade-api",  # common repo/docker working directory
        Path.cwd(),  # final fallback to current working directory
    ]

    seen: set[Path] = set()
    resolved: list[Path] = []
    for path in candidates:
        try:
            absolute = path.expanduser().resolve()
        except OSError:
            continue
        if absolute not in seen:
            seen.add(absolute)
            resolved.append(absolute)
    return resolved


def _detect_api_root() -> Path:
    """Pick a sensible API root that actually contains Alembic assets."""

    default_root = MODULE_DIR.parent.parent
    for candidate in _candidate_api_roots():
        if (candidate / "alembic.ini").exists() and (candidate / "migrations").exists():
            return candidate
    return default_root


DEFAULT_API_ROOT = _detect_api_root()
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]
DEFAULT_ALEMBIC_INI = DEFAULT_API_ROOT / "alembic.ini"
DEFAULT_ALEMBIC_MIGRATIONS = DEFAULT_API_ROOT / "migrations"
# NOTE: Using @main until ade-engine tags are published.
DEFAULT_ENGINE_SPEC = "ade-engine @ git+https://github.com/clac-ca/ade-engine@main"
DEFAULT_FRONTEND_DIST_DIR = Path("apps/ade-web/dist")
DEFAULT_DATABASE_URL = "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable"
DEFAULT_DATABASE_AUTH_MODE = "password"
DEFAULT_BLOB_PREFIX = "workspaces"
DEFAULT_BLOB_REQUIRE_VERSIONING = True
DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP = False
DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_BLOB_MAX_CONCURRENCY = 4
DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES = 4 * 1024 * 1024  # 4 MiB
DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MiB

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 2000
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
MAX_SET_SIZE = 50  # cap for *_in lists
COUNT_STATEMENT_TIMEOUT_MS: int | None = None  # optional (Postgres), e.g., 500

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
                raise ValueError(f"{field_name} must be secs or 'Xs','Xm','Xh','Xd'") from None
            try:
                seconds = float(num) * _UNIT_SECONDS[unit]
            except ValueError as exc:
                raise ValueError(f"{field_name} must be secs or 'Xs','Xm','Xh','Xd'") from exc
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


def _resolve_path(value: Path | str | None, *, default: Path) -> Path:
    """Expand, absolutize, and resolve a configurable path."""

    if value in (None, ""):
        candidate = default
    elif isinstance(value, Path):
        candidate = value
    else:
        candidate = Path(str(value).strip())
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.expanduser().resolve()


def _normalize_pg_driver(drivername: str) -> str:
    if drivername in {"postgres", "postgresql"}:
        return "postgresql+psycopg"
    if drivername.startswith("postgresql+") and drivername != "postgresql+psycopg":
        return "postgresql+psycopg"
    return drivername


# ---- Settings ---------------------------------------------------------------


class Settings(BaseSettings):
    """FastAPI settings loaded from ADE_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        populate_by_name=True,
    )

    _jwt_secret_generated: bool = PrivateAttr(default=False)

    # Core
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "1.6.1"
    app_commit_sha: str = "unknown"
    api_docs_enabled: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    log_level: str = "INFO"
    safe_mode: bool = False

    # Server
    server_public_url: str = DEFAULT_PUBLIC_URL
    api_host: str | None = None
    api_port: int | None = Field(default=None, ge=1, le=65535)
    api_workers: int | None = Field(default=None, ge=1)
    frontend_url: str | None = None
    frontend_dist_dir: Path | None = Field(default=None)
    server_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    idempotency_key_ttl: timedelta = Field(default=timedelta(hours=24))

    # Paths
    api_root: Path = Field(default=DEFAULT_API_ROOT)
    alembic_ini_path: Path = Field(default=DEFAULT_ALEMBIC_INI)
    alembic_migrations_dir: Path = Field(default=DEFAULT_ALEMBIC_MIGRATIONS)

    # Storage (Azure Blob only)
    data_dir: Path = Field(default=DEFAULT_DATA_DIR)
    blob_account_url: str | None = Field(default=None)
    blob_connection_string: str | None = Field(default=None)
    blob_container: str | None = Field(default=None)
    blob_prefix: str = Field(default=DEFAULT_BLOB_PREFIX)
    blob_require_versioning: bool = Field(default=DEFAULT_BLOB_REQUIRE_VERSIONING)
    blob_create_container_on_startup: bool = Field(
        default=DEFAULT_BLOB_CREATE_CONTAINER_ON_STARTUP
    )
    blob_request_timeout_seconds: float = Field(
        default=DEFAULT_BLOB_REQUEST_TIMEOUT_SECONDS, gt=0
    )
    blob_max_concurrency: int = Field(default=DEFAULT_BLOB_MAX_CONCURRENCY, ge=1)
    blob_upload_chunk_size_bytes: int = Field(
        default=DEFAULT_BLOB_UPLOAD_CHUNK_SIZE_BYTES, ge=1
    )
    blob_download_chunk_size_bytes: int = Field(
        default=DEFAULT_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES, ge=1
    )
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    documents_upload_concurrency_limit: int | None = Field(8, ge=1)

    # Engine
    engine_spec: str = Field(
        default=DEFAULT_ENGINE_SPEC,
        validation_alias="ADE_ENGINE_PACKAGE_PATH",
    )

    # Database
    database_url: str = Field(..., description="Postgres database URL.")
    database_echo: bool = False
    database_log_level: str | None = None
    database_pool_size: int = Field(5, ge=1)
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_pool_recycle: int = Field(1800, ge=0)
    database_auth_mode: Literal["password", "managed_identity"] = Field(
        default=DEFAULT_DATABASE_AUTH_MODE
    )
    database_sslrootcert: str | None = Field(default=None)

    # JWT
    jwt_secret: SecretStr | None = Field(
        default=None,
        description=(
            "Secret used to sign session cookies and bearer tokens; set to a long random string "
            "(e.g. python - <<'PY'\\nimport secrets; print(secrets.token_urlsafe(64))\\nPY)"
        ),
    )
    jwt_algorithm: str = "HS256"
    jwt_access_ttl: timedelta = Field(default=timedelta(hours=1))

    # Sessions
    session_cookie_name: str = "ade_session"
    session_csrf_cookie_name: str = "ade_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_access_ttl: timedelta = Field(default=timedelta(days=14))

    # Auth policy
    api_key_prefix_length: int = Field(12, ge=6, le=32)
    api_key_secret_bytes: int = Field(32, ge=16, le=128)
    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))
    allow_public_registration: bool = False
    auth_disabled: bool = False
    auth_disabled_user_email: str = "developer@example.com"
    auth_disabled_user_name: str | None = "Development User"
    auth_force_sso: bool = False
    auth_sso_auto_provision: bool = False
    auth_sso_providers_json: str | None = None
    sso_encryption_key: SecretStr | None = None

    # Runs
    preview_timeout_seconds: float = Field(10, gt=0)

    # ---- Validators ----

    @field_validator("server_public_url", mode="before")
    @classmethod
    def _v_public_url(cls, v: Any) -> str:
        s = str(v).strip()
        p = urlparse(s)
        if p.scheme not in {"http", "https"} or not p.netloc:
            raise ValueError("ADE_SERVER_PUBLIC_URL must be an http(s) URL")
        return s.rstrip("/")

    @field_validator("frontend_url", mode="before")
    @classmethod
    def _v_frontend_url(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        s = str(v).strip()
        p = urlparse(s)
        if p.scheme not in {"http", "https"} or not p.netloc:
            raise ValueError("ADE_FRONTEND_URL must be an http(s) URL")
        return s.rstrip("/")

    @field_validator("log_level", mode="before")
    @classmethod
    def _v_log_level(cls, v: Any) -> str:
        s = ("" if v is None else str(v).strip()).upper()
        return s or "INFO"

    @field_validator("database_log_level", mode="before")
    @classmethod
    def _v_db_log_level(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return cls._v_log_level(v)

    @field_validator("database_url", mode="before")
    @classmethod
    def _v_database_url(cls, v: Any) -> str:
        if v in (None, ""):
            raise ValueError("ADE_DATABASE_URL is required.")
        return str(v).strip()

    @field_validator("database_sslrootcert", mode="before")
    @classmethod
    def _v_database_sslrootcert(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip()

    @field_validator("server_cors_origins", mode="before")
    @classmethod
    def _v_cors(cls, v: Any) -> list[str]:
        return _list_from_env(v, default=DEFAULT_CORS_ORIGINS)

    @field_validator("auth_sso_providers_json", mode="before")
    @classmethod
    def _v_auth_sso_providers_json(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("database_auth_mode", mode="before")
    @classmethod
    def _v_db_auth_mode(cls, v: Any) -> str:
        if v in (None, ""):
            return DEFAULT_DATABASE_AUTH_MODE
        mode = str(v).strip().lower()
        if mode not in {"password", "managed_identity"}:
            raise ValueError("ADE_DATABASE_AUTH_MODE must be 'password' or 'managed_identity'")
        return mode

    @field_validator("blob_account_url", mode="before")
    @classmethod
    def _v_blob_account_url(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        s = str(v).strip()
        if not s:
            return None
        p = urlparse(s)
        if p.scheme not in {"http", "https"} or not p.netloc:
            raise ValueError("ADE_BLOB_ACCOUNT_URL must be an http(s) URL")
        return s.rstrip("/")

    @field_validator("blob_connection_string", mode="before")
    @classmethod
    def _v_blob_connection_string(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("blob_container", mode="before")
    @classmethod
    def _v_blob_container(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("blob_prefix", mode="before")
    @classmethod
    def _v_blob_prefix(cls, v: Any) -> str:
        if v in (None, ""):
            return DEFAULT_BLOB_PREFIX
        cleaned = str(v).strip().strip("/")
        return cleaned or DEFAULT_BLOB_PREFIX


    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _v_jwt_secret(cls, v: Any) -> SecretStr:
        if v is None:
            return None  # handled in finalize
        raw = v.get_secret_value() if isinstance(v, SecretStr) else str(v or "").strip()
        if raw and set(raw) == {"*"}:
            return None
        if raw and len(raw) < 32:
            raise ValueError(
                "ADE_JWT_SECRET must be at least 32 characters. Use a long random string "
                "(e.g. python - <<'PY'\\nimport secrets; print(secrets.token_urlsafe(64))\\nPY)."
            )
        return SecretStr(raw) if raw else None

    @field_validator(
        "jwt_access_ttl",
        "session_access_ttl",
        "failed_login_lock_duration",
        "storage_document_retention_period",
        "idempotency_key_ttl",
        mode="before",
    )
    @classmethod
    def _v_durations(cls, v: Any, info: ValidationInfo) -> timedelta:
        return _parse_duration(v, field_name=info.field_name)

    @field_validator("frontend_dist_dir", mode="before")
    @classmethod
    def _v_frontend_dist_dir(cls, v: Any) -> Path | None:
        if v in (None, ""):
            return None
        return Path(v)

    # ---- Finalize: resolve paths & validate OIDC ----

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        self.api_root = _resolve_path(self.api_root, default=DEFAULT_API_ROOT)
        self.alembic_ini_path = _resolve_path(self.alembic_ini_path, default=DEFAULT_ALEMBIC_INI)
        self.alembic_migrations_dir = _resolve_path(
            self.alembic_migrations_dir, default=DEFAULT_ALEMBIC_MIGRATIONS
        )

        self.data_dir = _resolve_path(self.data_dir, default=DEFAULT_DATA_DIR)

        if self.frontend_dist_dir:
            self.frontend_dist_dir = _resolve_path(
                self.frontend_dist_dir, default=DEFAULT_FRONTEND_DIST_DIR
            )

        if not self.frontend_url:
            self.frontend_url = self.server_public_url

        if not self.database_url:
            raise ValueError("ADE_DATABASE_URL is required.")

        url = make_url(self.database_url)
        drivername = _normalize_pg_driver(url.drivername)
        if not drivername.startswith("postgresql"):
            raise ValueError("Only Postgres is supported. Use postgresql+psycopg://... for ADE_DATABASE_URL.")
        if drivername != url.drivername:
            url = url.set(drivername=drivername)

        required_values = {
            "host": url.host,
            "user": url.username,
            "database": url.database,
        }
        missing = [name for name, value in required_values.items() if not value]
        if self.database_auth_mode == "password" and not url.password:
            missing.append("password")
        if missing:
            raise ValueError(
                "ADE_DATABASE_URL is missing required parts: " + ", ".join(missing)
            )

        if self.database_sslrootcert:
            query = dict(url.query or {})
            query["sslrootcert"] = self.database_sslrootcert
            url = url.set(query=query)

        self.database_url = url.render_as_string(hide_password=False)

        if not self.blob_container:
            raise ValueError("ADE_BLOB_CONTAINER is required.")
        if self.blob_connection_string and self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_ACCOUNT_URL must be unset when ADE_BLOB_CONNECTION_STRING is provided."
            )
        if not self.blob_connection_string and not self.blob_account_url:
            raise ValueError(
                "ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL is required."
            )

        if self.jwt_secret is None or not self.jwt_secret.get_secret_value().strip():
            self.jwt_secret = SecretStr(secrets.token_urlsafe(64))
            self._jwt_secret_generated = True

        return self

    @property
    def workspaces_dir(self) -> Path:
        return (self.data_dir / "workspaces").resolve()

    @property
    def documents_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def configs_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def runs_dir(self) -> Path:
        return self.workspaces_dir

    @property
    def venvs_dir(self) -> Path:
        return (self.data_dir / "venvs").resolve()

    @property
    def pip_cache_dir(self) -> Path:
        return (self.data_dir / "cache" / "pip").resolve()

    # ---- Convenience ----

    @property
    def jwt_secret_value(self) -> str:
        return self.jwt_secret.get_secret_value()

    @property
    def jwt_secret_generated(self) -> bool:
        return self._jwt_secret_generated


@lru_cache(maxsize=1)
def _build_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    return _build_settings()


def reload_settings() -> Settings:
    _build_settings.cache_clear()
    return _build_settings()


__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_PUBLIC_URL",
    "Settings",
    "get_settings",
    "reload_settings",
]
