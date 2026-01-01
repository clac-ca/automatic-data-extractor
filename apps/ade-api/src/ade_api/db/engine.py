"""Async engine management for ADE."""

from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.engine import URL, Connection, Engine, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from ade_api.settings import Settings, get_settings

try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    DefaultAzureCredential = None  # type: ignore[assignment]
    _default_credential_import_error = exc
else:  # pragma: no cover - optional dependency
    _default_credential_import_error = None

_SQL_COPT_SS_ACCESS_TOKEN = 1256
_AZURE_SQL_SCOPE = "https://database.windows.net/.default"

_ENGINE: AsyncEngine | None = None
_ENGINE_KEY: tuple[Any, ...] | None = None
_BOOTSTRAP_LOCK = asyncio.Lock()
_BOOTSTRAPPED_URLS: set[str] = set()

logger = logging.getLogger(__name__)


def _is_managed_identity(settings: Settings, url: URL) -> bool:
    return settings.database_auth_mode == "managed_identity" and url.get_backend_name() == "mssql"


def _sanitize_mssql_query(query: dict[str, Any], *, managed_identity: bool) -> dict[str, Any]:
    sanitized = dict(query)
    if managed_identity:
        for key in (
            "Authentication",
            "authentication",
            "Trusted_Connection",
            "trusted_connection",
        ):
            sanitized.pop(key, None)
    return sanitized


def build_database_url(settings: Settings) -> URL:
    url = make_url(settings.database_dsn)
    managed_identity = _is_managed_identity(settings, url)

    if managed_identity and url.get_backend_name() != "mssql":
        raise ValueError("Managed identity is only supported with mssql+pyodbc")

    if url.get_backend_name() == "mssql":
        query = _sanitize_mssql_query(dict(url.query or {}), managed_identity=managed_identity)
        url = url.set(query=query)
        if managed_identity:
            url = URL.create(
                drivername=url.drivername,
                username=None,
                password=None,
                host=url.host,
                port=url.port,
                database=url.database,
                query=url.query,
            )

    return url


def _managed_identity_token_provider(settings: Settings) -> Callable[[], bytes]:
    if DefaultAzureCredential is None:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Managed identity requires azure-identity; install azure-identity to enable "
            "ADE_DATABASE_AUTH_MODE=managed_identity"
        ) from _default_credential_import_error

    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.database_mi_client_id or None,
    )

    def _get_token() -> bytes:
        token = credential.get_token(_AZURE_SQL_SCOPE).token
        token_bytes = token.encode("utf-16-le")
        return struct.pack("<I", len(token_bytes)) + token_bytes

    return _get_token


def _managed_identity_injector(token_provider: Callable[[], bytes]) -> Callable[..., None]:
    def _inject(_dialect, _conn_rec, _cargs, cparams):
        attrs_before = dict(cparams.pop("attrs_before", {}) or {})
        attrs_before[_SQL_COPT_SS_ACCESS_TOKEN] = token_provider()

        cparams.pop("user", None)
        cparams.pop("username", None)
        cparams.pop("password", None)
        for key in (
            "Authentication",
            "authentication",
            "Trusted_Connection",
            "trusted_connection",
        ):
            cparams.pop(key, None)

        cparams["attrs_before"] = attrs_before

    return _inject


def attach_managed_identity(sync_engine: Engine, settings: Settings) -> None:
    if getattr(sync_engine, "_ade_mi_attached", False):
        return

    token_provider = _managed_identity_token_provider(settings)
    injector = _managed_identity_injector(token_provider)
    event.listen(sync_engine, "do_connect", injector, insert=True)
    sync_engine._ade_mi_attached = True


def _cache_key(settings: Settings) -> tuple[Any, ...]:
    url = build_database_url(settings)
    return (
        url.render_as_string(hide_password=False),
        settings.database_auth_mode,
        settings.database_mi_client_id,
        settings.database_echo,
        settings.database_pool_size,
        settings.database_max_overflow,
        settings.database_pool_timeout,
    )


def is_sqlite_memory_url(url: URL) -> bool:
    database = (url.database or "").strip()
    if not database or database == ":memory:":
        return True
    if database.startswith("file:"):
        query = dict(url.query or {})
        if query.get("mode") == "memory":
            return True
    return False


def ensure_sqlite_database_directory(url: URL) -> None:
    """Ensure a filesystem-backed SQLite database can be created."""

    database = (url.database or "").strip()
    if not database or database == ":memory:" or database.startswith("file:"):
        return
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


def _assert_pyodbc_available(url: URL) -> None:
    """Raise a clearer error when pyodbc/system drivers are missing for MSSQL."""

    if url.get_backend_name() != "mssql":
        return

    try:
        import pyodbc  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on host system deps
        msg = (
            "pyodbc could not load the ODBC driver. Install unixODBC and the "
            "Microsoft ODBC Driver 18 for SQL Server to use Azure SQL. "
            "On Debian/Ubuntu add the Microsoft repo "
            "(`curl -sSL -O https://packages.microsoft.com/config/ubuntu/"
            "$(grep VERSION_ID /etc/os-release | cut -d '\"' -f 2)/"
            "packages-microsoft-prod.deb && "
            "sudo dpkg -i packages-microsoft-prod.deb && sudo apt-get update`) "
            "then install with `sudo ACCEPT_EULA=Y apt-get install -y unixodbc msodbcsql18`. "
            "For local dev you can avoid this by using SQLite "
            "(ADE_DATABASE_DSN=sqlite+aiosqlite:///./data/db/ade.sqlite). "
            f"DSN: {url.render_as_string(hide_password=True)}"
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc


def _create_engine(settings: Settings) -> AsyncEngine:
    url = build_database_url(settings)
    _assert_pyodbc_available(url)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": settings.database_echo,
        "pool_pre_ping": True,
    }

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = settings.database_pool_timeout
        engine_kwargs["poolclass"] = StaticPool
        if not is_sqlite_memory_url(url):
            ensure_sqlite_database_directory(url)
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow
        engine_kwargs["pool_timeout"] = settings.database_pool_timeout

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    engine = create_async_engine(url.render_as_string(hide_password=False), **engine_kwargs)

    if _is_managed_identity(settings, url):
        attach_managed_identity(engine.sync_engine, settings)

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return a cached async engine matching the active settings."""

    global _ENGINE, _ENGINE_KEY
    settings = settings or get_settings()
    key = _cache_key(settings)
    if _ENGINE is None or _ENGINE_KEY != key:
        if _ENGINE is not None:
            _ENGINE.sync_engine.dispose()
        _ENGINE = _create_engine(settings)
        _ENGINE_KEY = key
    return _ENGINE


def reset_database_state() -> None:
    """Dispose cached engine and associated session factories."""

    global _ENGINE, _ENGINE_KEY
    if _ENGINE is not None:
        _ENGINE.sync_engine.dispose()
    _ENGINE = None
    _ENGINE_KEY = None

    try:
        from . import session as session_module
    except ImportError:
        session_module = None

    if session_module is not None:
        session_module.reset_session_state()

    reset_bootstrap_state()


def _load_alembic_config(settings: Settings) -> Config:
    config_path = settings.alembic_ini_path
    if not config_path.exists():
        msg = f"Alembic configuration not found at {config_path}"
        raise FileNotFoundError(msg)
    config = Config(str(config_path))
    # Preserve the API's logging configuration when migrations run in-process.
    config.attributes["configure_logger"] = False
    config.set_main_option("script_location", str(settings.alembic_migrations_dir))
    return config


def _upgrade_database(settings: Settings, connection: Connection | None = None) -> None:
    config = _load_alembic_config(settings)
    config.set_main_option("sqlalchemy.url", render_sync_url(settings))
    if connection is not None:
        config.attributes["connection"] = connection
    command.upgrade(config, "head")


def _apply_migrations(settings: Settings) -> None:
    url = build_database_url(settings)
    _assert_pyodbc_available(url)
    if url.get_backend_name() == "sqlite":
        ensure_sqlite_database_directory(url)
    try:
        _upgrade_database(settings)
    except OperationalError:
        if url.get_backend_name() == "mssql":
            msg = (
                "Failed to connect to SQL Server / Azure SQL (login timeout). "
                f"DSN: {url.render_as_string(hide_password=True)}. "
                "Check network/firewall rules to port 1433, server name, "
                "credentials or managed identity, and that the ODBC driver can "
                "reach the host. "
                "For local dev you can switch to SQLite with "
                "ADE_DATABASE_DSN=sqlite+aiosqlite:///./data/db/ade.sqlite."
            )
            logger.error(msg, exc_info=True)
        raise


async def ensure_database_ready(settings: Settings | None = None) -> None:
    """Create the database and apply migrations if needed."""

    resolved = settings or get_settings()
    url = build_database_url(resolved)
    bootstrap_key = f"{resolved.database_auth_mode}:{render_sync_url(resolved)}"

    async with _BOOTSTRAP_LOCK:
        if bootstrap_key in _BOOTSTRAPPED_URLS:
            return

        if url.get_backend_name() == "sqlite" and is_sqlite_memory_url(url):
            engine = get_engine(resolved)

            async with engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: _upgrade_database(resolved, connection=sync_connection)
                )
        else:
            await asyncio.to_thread(_apply_migrations, resolved)
        _BOOTSTRAPPED_URLS.add(bootstrap_key)


async def check_database_ready(settings: Settings | None = None) -> None:
    """Verify database connectivity without running migrations."""

    resolved = settings or get_settings()
    engine = get_engine(resolved)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("database.readiness.failed", exc_info=exc)
        raise


def reset_bootstrap_state() -> None:
    """Clear cached bootstrap results (useful for tests)."""

    _BOOTSTRAPPED_URLS.clear()


def engine_cache_key(settings: Settings) -> tuple[Any, ...]:
    """Expose the cache key used for engine/session reuse."""

    return _cache_key(settings)


def render_sync_url(database: Settings | str) -> str:
    """Return a synchronous SQLAlchemy URL for Alembic migrations."""

    if isinstance(database, Settings):
        url = build_database_url(database)
    else:
        url = make_url(database)
    driver = url.get_backend_name()
    sync_url = url.set(drivername=driver)
    return sync_url.render_as_string(hide_password=False)


__all__ = [
    "attach_managed_identity",
    "build_database_url",
    "check_database_ready",
    "engine_cache_key",
    "ensure_database_ready",
    "ensure_sqlite_database_directory",
    "is_sqlite_memory_url",
    "get_engine",
    "render_sync_url",
    "reset_database_state",
    "reset_bootstrap_state",
]
