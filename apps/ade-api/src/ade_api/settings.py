"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

from pydantic import Field, PrivateAttr, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource

# ---- Defaults ---------------------------------------------------------------

MODULE_DIR = Path(__file__).resolve().parent


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
DEFAULT_WEB_DIR = MODULE_DIR / "web"
DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]
DEFAULT_STORAGE_ROOT = Path("./data")        # resolve later
DEFAULT_WORKSPACES_DIR = DEFAULT_STORAGE_ROOT / "workspaces"
DEFAULT_DB_FILENAME = "ade.sqlite"
DEFAULT_ALEMBIC_INI = DEFAULT_API_ROOT / "alembic.ini"
DEFAULT_ALEMBIC_MIGRATIONS = DEFAULT_API_ROOT / "migrations"
DEFAULT_DOCUMENTS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_CONFIGS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_VENVS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_RUNS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_PIP_CACHE_DIR = DEFAULT_STORAGE_ROOT / "cache" / "pip"
DEFAULT_SQLITE_PATH = DEFAULT_STORAGE_ROOT / "db" / DEFAULT_DB_FILENAME
DEFAULT_ENGINE_SPEC = "apps/ade-engine"
DEFAULT_BUILD_TIMEOUT = timedelta(seconds=600)
DEFAULT_BUILD_ENSURE_WAIT = timedelta(seconds=30)
DEFAULT_BUILD_RETENTION = timedelta(days=30)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SORT_FIELDS = 3
MIN_SEARCH_LEN = 2
MAX_SEARCH_LEN = 128
MAX_SET_SIZE = 50                  # cap for *_in lists
COUNT_STATEMENT_TIMEOUT_MS: int | None = None  # optional (Postgres), e.g., 500

_LENIENT_LIST_FIELDS = {"server_cors_origins", "oidc_scopes"}

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
                raise ValueError(
                    f"{field_name} must be secs or 'Xs','Xm','Xh','Xd'"
                ) from None
            try:
                seconds = float(num) * _UNIT_SECONDS[unit]
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must be secs or 'Xs','Xm','Xh','Xd'"
                ) from exc
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
    return candidate.expanduser().resolve()


# ---- Settings ---------------------------------------------------------------

class _LenientEnvSettingsSource(EnvSettingsSource):
    """Environment source that preserves raw strings for list-like fields."""

    lenient_fields: ClassVar[set[str]] = _LENIENT_LIST_FIELDS

    def prepare_field_value(
        self,
        field_name: str,
        field,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in self.lenient_fields and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _LenientDotEnvSettingsSource(DotEnvSettingsSource):
    """Dotenv source that preserves raw strings for list-like fields."""

    lenient_fields: ClassVar[set[str]] = _LENIENT_LIST_FIELDS

    def prepare_field_value(
        self,
        field_name: str,
        field,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in self.lenient_fields and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    """FastAPI settings loaded from ADE_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADE_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    _explicit_init_fields: set[str] = PrivateAttr(default_factory=set)

    def __init__(self, **data: Any):
        explicit = set(data.keys())
        super().__init__(**data)
        object.__setattr__(self, "_explicit_init_fields", explicit)
        if "workspaces_dir" in explicit:
            self._apply_workspaces_override(explicit)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        env_source = _LenientEnvSettingsSource(
            settings_cls,
            case_sensitive=getattr(env_settings, "case_sensitive", None),
            env_prefix=getattr(env_settings, "env_prefix", None),
            env_nested_delimiter=getattr(env_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(env_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(env_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(env_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(env_settings, "env_parse_enums", None),
        )
        dotenv_source = _LenientDotEnvSettingsSource(
            settings_cls,
            env_file=getattr(dotenv_settings, "env_file", None),
            env_file_encoding=getattr(dotenv_settings, "env_file_encoding", None),
            case_sensitive=getattr(dotenv_settings, "case_sensitive", None),
            env_prefix=getattr(dotenv_settings, "env_prefix", None),
            env_nested_delimiter=getattr(dotenv_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(dotenv_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(dotenv_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(dotenv_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(dotenv_settings, "env_parse_enums", None),
        )
        return (init_settings, env_source, dotenv_source, file_secret_settings)

    def _apply_workspaces_override(self, explicit_fields: set[str]) -> None:
        """Align dependent storage roots when workspaces_dir is provided explicitly."""

        if "documents_dir" not in explicit_fields:
            self.documents_dir = self.workspaces_dir
        if "configs_dir" not in explicit_fields:
            self.configs_dir = self.workspaces_dir
        if "venvs_dir" not in explicit_fields:
            self.venvs_dir = self.workspaces_dir
        if "runs_dir" not in explicit_fields:
            self.runs_dir = self.workspaces_dir

    # Core
    debug: bool = False
    dev_mode: bool = False
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "0.2.0"
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

    # Paths
    api_root: Path = Field(default=DEFAULT_API_ROOT)
    web_dir: Path = Field(default=DEFAULT_WEB_DIR)
    alembic_ini_path: Path = Field(default=DEFAULT_ALEMBIC_INI)
    alembic_migrations_dir: Path = Field(default=DEFAULT_ALEMBIC_MIGRATIONS)

    # Storage
    workspaces_dir: Path = Field(default=DEFAULT_WORKSPACES_DIR)
    documents_dir: Path = Field(default=DEFAULT_DOCUMENTS_DIR)
    configs_dir: Path = Field(default=DEFAULT_CONFIGS_DIR)
    venvs_dir: Path = Field(default=DEFAULT_VENVS_DIR)
    runs_dir: Path = Field(default=DEFAULT_RUNS_DIR)
    pip_cache_dir: Path = Field(default=DEFAULT_PIP_CACHE_DIR)
    storage_upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)
    storage_document_retention_period: timedelta = Field(default=timedelta(days=30))
    secret_key: SecretStr = Field(
        default=SecretStr("ZGV2ZWxvcG1lbnQtY29uZmlnLXNlY3JldC1rZXktMzI="),
        description="Base64-encoded 32 byte secret key",
    )

    # Builds
    engine_spec: str = Field(default=DEFAULT_ENGINE_SPEC)
    python_bin: str | None = Field(default=None)
    build_timeout: timedelta = Field(default=DEFAULT_BUILD_TIMEOUT)
    build_ensure_wait: timedelta = Field(default=DEFAULT_BUILD_ENSURE_WAIT)
    build_ttl: timedelta | None = Field(default=None)
    build_retention: timedelta | None = Field(default=DEFAULT_BUILD_RETENTION)

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
    auth_disabled: bool = False
    auth_disabled_user_email: str = "developer@example.test"
    auth_disabled_user_name: str | None = "Development User"

    # Runs & workers
    max_concurrency: int | None = Field(default=None, ge=1)
    queue_size: int | None = Field(default=None, ge=1)
    run_timeout_seconds: int | None = Field(default=None, ge=1)  # accepts '5m', '300'
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

    @field_validator("build_timeout", "build_ensure_wait", mode="before")
    @classmethod
    def _v_build_required(cls, v: Any, info: ValidationInfo) -> timedelta:
        return _parse_duration(v, field_name=info.field_name)

    @field_validator("build_ttl", "build_retention", mode="before")
    @classmethod
    def _v_build_optional(cls, v: Any, info: ValidationInfo) -> timedelta | None:
        if v in (None, ""):
            return None
        return _parse_duration(v, field_name=info.field_name)

    @field_validator("run_timeout_seconds", mode="before")
    @classmethod
    def _v_run_timeout(cls, v: Any) -> int | None:
        if v in (None, ""):
            return None
        return int(_parse_duration(v, field_name="run_timeout_seconds").total_seconds())

    @field_validator("secret_key", mode="before")
    @classmethod
    def _v_secret_key(cls, v: Any) -> SecretStr:
        if v is None:
            raise ValueError("ADE_SECRET_KEY must be provided")
        raw = v.get_secret_value() if isinstance(v, SecretStr) else str(v).strip()
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
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
    def _finalize(self) -> Settings:
        self.api_root = _resolve_path(self.api_root, default=DEFAULT_API_ROOT)
        self.web_dir = _resolve_path(self.web_dir, default=DEFAULT_WEB_DIR)
        self.alembic_ini_path = _resolve_path(
            self.alembic_ini_path, default=DEFAULT_ALEMBIC_INI
        )
        self.alembic_migrations_dir = _resolve_path(
            self.alembic_migrations_dir, default=DEFAULT_ALEMBIC_MIGRATIONS
        )

        workspaces_explicit = "workspaces_dir" in self._explicit_init_fields
        documents_explicit = "documents_dir" in self._explicit_init_fields
        configs_explicit = "configs_dir" in self._explicit_init_fields
        venvs_explicit = "venvs_dir" in self._explicit_init_fields
        runs_explicit = "runs_dir" in self._explicit_init_fields

        self.workspaces_dir = _resolve_path(
            self.workspaces_dir, default=DEFAULT_WORKSPACES_DIR
        )
        if workspaces_explicit and not documents_explicit:
            self.documents_dir = self.workspaces_dir
        elif "documents_dir" not in self.model_fields_set:
            self.documents_dir = self.workspaces_dir
        if workspaces_explicit and not configs_explicit:
            self.configs_dir = self.workspaces_dir
        elif "configs_dir" not in self.model_fields_set:
            self.configs_dir = self.workspaces_dir
        if workspaces_explicit and not venvs_explicit:
            self.venvs_dir = self.workspaces_dir
        elif "venvs_dir" not in self.model_fields_set:
            self.venvs_dir = self.workspaces_dir
        if workspaces_explicit and not runs_explicit:
            self.runs_dir = self.workspaces_dir
        elif "runs_dir" not in self.model_fields_set:
            self.runs_dir = self.workspaces_dir
        self.documents_dir = _resolve_path(
            self.documents_dir, default=self.workspaces_dir
        )
        self.configs_dir = _resolve_path(self.configs_dir, default=self.workspaces_dir)
        self.venvs_dir = _resolve_path(self.venvs_dir, default=self.workspaces_dir)
        self.runs_dir = _resolve_path(self.runs_dir, default=self.workspaces_dir)
        self.pip_cache_dir = _resolve_path(
            self.pip_cache_dir, default=DEFAULT_PIP_CACHE_DIR
        )

        if not self.database_dsn:
            sqlite = _resolve_path(DEFAULT_SQLITE_PATH, default=DEFAULT_SQLITE_PATH)
            self.database_dsn = f"sqlite+aiosqlite:///{sqlite.as_posix()}"

        oidc_config = {
            "ADE_OIDC_CLIENT_ID": self.oidc_client_id,
            "ADE_OIDC_CLIENT_SECRET": self.oidc_client_secret,
            "ADE_OIDC_ISSUER": self.oidc_issuer,
            "ADE_OIDC_REDIRECT_URL": self.oidc_redirect_url,
        }
        provided_oidc_values = [name for name, val in oidc_config.items() if val]

        if not self.oidc_enabled and len(provided_oidc_values) == len(oidc_config):
            self.oidc_enabled = True

        if self.oidc_enabled:
            missing = [name for name, val in oidc_config.items() if not val]
            if missing:
                raise ValueError("OIDC enabled but missing: " + ", ".join(missing))
            if "openid" not in self.oidc_scopes:
                self.oidc_scopes = ["openid", *self.oidc_scopes]
            if self.oidc_redirect_url and self.oidc_redirect_url.startswith("/"):
                self.oidc_redirect_url = f"{self.server_public_url}{self.oidc_redirect_url}"
        else:
            # If disabled, discourage partial config that hints at a misconfigured env
            if provided_oidc_values:
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
def _build_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    return _build_settings()


def reload_settings() -> Settings:
    _build_settings.cache_clear()
    return _build_settings()


__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_DB_FILENAME",
    "DEFAULT_PUBLIC_URL",
    "Settings",
    "get_settings",
    "reload_settings",
]
