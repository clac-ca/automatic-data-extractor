"""ADE settings (clean-slate, conventional Pydantic v2)."""

from __future__ import annotations

import json
import secrets
import tempfile
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Literal
from urllib.parse import urlparse

from pydantic import Field, PrivateAttr, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource
from sqlalchemy.engine import URL, make_url

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
DEFAULT_STORAGE_ROOT = Path("./data")        # resolve later
DEFAULT_PUBLIC_URL = "http://localhost:8000"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]
DEFAULT_WORKSPACES_DIR = DEFAULT_STORAGE_ROOT / "workspaces"
DEFAULT_DB_FILENAME = "ade.sqlite"
DEFAULT_ALEMBIC_INI = DEFAULT_API_ROOT / "alembic.ini"
DEFAULT_ALEMBIC_MIGRATIONS = DEFAULT_API_ROOT / "migrations"
DEFAULT_DOCUMENTS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_CONFIGS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_VENVS_DIR = Path(tempfile.gettempdir()) / "ade-venvs"
DEFAULT_RUNS_DIR = DEFAULT_WORKSPACES_DIR
DEFAULT_PIP_CACHE_DIR = DEFAULT_STORAGE_ROOT / "cache" / "pip"
DEFAULT_SQLITE_PATH = DEFAULT_STORAGE_ROOT / "db" / DEFAULT_DB_FILENAME
DEFAULT_ENGINE_SPEC = "apps/ade-engine"
DEFAULT_BUILD_TIMEOUT = timedelta(seconds=600)
DEFAULT_BUILD_ENSURE_WAIT = timedelta(seconds=30)

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
    _jwt_secret_generated: bool = PrivateAttr(default=False)

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
        if "runs_dir" not in explicit_fields:
            self.runs_dir = self.workspaces_dir

    # Core
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "1.6.1"
    api_docs_enabled: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    logging_level: str = "INFO"
    safe_mode: bool = False

    # Server
    server_public_url: str = DEFAULT_PUBLIC_URL
    frontend_url: str | None = None
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

    # Builds
    engine_spec: str = Field(default=DEFAULT_ENGINE_SPEC)
    python_bin: str | None = Field(default=None)
    build_timeout: timedelta = Field(default=DEFAULT_BUILD_TIMEOUT)
    build_ensure_wait: timedelta = Field(default=DEFAULT_BUILD_ENSURE_WAIT)
    build_ttl: timedelta | None = Field(default=None)

    # Database
    database_dsn: str | None = None
    database_echo: bool = False
    database_pool_size: int = Field(5, ge=1)       # ignored by sqlite; relevant for Postgres
    database_max_overflow: int = Field(10, ge=0)
    database_pool_timeout: int = Field(30, gt=0)
    database_auth_mode: Literal["sql_password", "managed_identity"] = Field(
        default="sql_password"
    )
    database_mi_client_id: str | None = None

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
    jwt_refresh_ttl: timedelta = Field(default=timedelta(days=14))

    # Sessions
    session_cookie_name: str = "ade_session"
    session_refresh_cookie_name: str = "ade_refresh"
    session_csrf_cookie_name: str = "ade_csrf"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_last_seen_interval: timedelta = Field(default=timedelta(minutes=5))

    # Auth policy
    api_key_prefix_length: int = Field(12, ge=6, le=32)
    api_key_secret_bytes: int = Field(32, ge=16, le=128)
    failed_login_lock_threshold: int = Field(5, ge=1)
    failed_login_lock_duration: timedelta = Field(default=timedelta(minutes=5))
    auth_disabled: bool = False
    auth_disabled_user_email: str = "developer@example.com"
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

    @field_validator("database_auth_mode", mode="before")
    @classmethod
    def _v_db_auth_mode(cls, v: Any) -> str:
        if v in (None, ""):
            return "sql_password"
        mode = str(v).strip().lower()
        if mode not in {"sql_password", "managed_identity"}:
            raise ValueError(
                "ADE_DATABASE_AUTH_MODE must be 'sql_password' or 'managed_identity'"
            )
        return mode

    @field_validator("database_mi_client_id", mode="before")
    @classmethod
    def _v_db_mi_client(cls, v: Any) -> str | None:
        if v in (None, ""):
            return None
        return str(v).strip()

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

    @field_validator("build_ttl", mode="before")
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

        self.workspaces_dir = _resolve_path(
            self.workspaces_dir, default=DEFAULT_WORKSPACES_DIR
        )
        if "documents_dir" not in self.model_fields_set:
            self.documents_dir = self.workspaces_dir
        if "configs_dir" not in self.model_fields_set:
            self.configs_dir = self.workspaces_dir
        if "runs_dir" not in self.model_fields_set:
            self.runs_dir = self.workspaces_dir
        self.documents_dir = _resolve_path(
            self.documents_dir, default=self.workspaces_dir
        )
        self.configs_dir = _resolve_path(self.configs_dir, default=self.workspaces_dir)
        self.venvs_dir = _resolve_path(self.venvs_dir, default=DEFAULT_VENVS_DIR)
        self.runs_dir = _resolve_path(self.runs_dir, default=self.workspaces_dir)
        self.pip_cache_dir = _resolve_path(
            self.pip_cache_dir, default=DEFAULT_PIP_CACHE_DIR
        )

        if not self.frontend_url:
            self.frontend_url = self.server_public_url

        if not self.database_dsn:
            sqlite = _resolve_path(DEFAULT_SQLITE_PATH, default=DEFAULT_SQLITE_PATH)
            self.database_dsn = f"sqlite+aiosqlite:///{sqlite.as_posix()}"

        url = make_url(self.database_dsn)
        query = dict(url.query or {})

        if url.get_backend_name() == "mssql" and "driver" not in query:
            query["driver"] = "ODBC Driver 18 for SQL Server"

        # SQL Server async connectivity: prefer aioodbc (required for SQLAlchemy async)
        if url.get_backend_name() == "mssql" and not url.drivername.startswith("mssql+aioodbc"):
            url = url.set(drivername="mssql+aioodbc")

        if self.database_auth_mode == "managed_identity":
            if url.get_backend_name() != "mssql":
                raise ValueError(
                    "ADE_DATABASE_AUTH_MODE=managed_identity requires an mssql+pyodbc DSN"
                )
            url = URL.create(
                drivername=url.drivername,
                username=None,
                password=None,
                host=url.host,
                port=url.port,
                database=url.database,
                query=query,
            )
        elif query != url.query:
            url = url.set(query=query)

        self.database_dsn = url.render_as_string(hide_password=False)

        if self.jwt_secret is None or not self.jwt_secret.get_secret_value().strip():
            self.jwt_secret = SecretStr(secrets.token_urlsafe(64))
            self._jwt_secret_generated = True

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
    "DEFAULT_DB_FILENAME",
    "DEFAULT_PUBLIC_URL",
    "Settings",
    "get_settings",
    "reload_settings",
]
