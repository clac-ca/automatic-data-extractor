"""Shared database engine helpers (Postgres only)."""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Iterator, Protocol

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

# Optional dependency (Managed Identity)
try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:
    DefaultAzureCredential = None  # type: ignore[assignment]

DEFAULT_AZURE_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


class DatabaseSettings(Protocol):
    database_url: str | URL
    database_echo: bool
    database_auth_mode: str
    database_sslrootcert: str | None
    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout: int
    database_pool_recycle: int
    database_connect_timeout_seconds: int | None
    database_statement_timeout_ms: int | None


def _apply_sslrootcert(url: URL, sslrootcert: str | None) -> URL:
    if not sslrootcert:
        return url
    query = dict(url.query or {})
    query["sslrootcert"] = sslrootcert
    return url.set(query=query)


_STATEMENT_TIMEOUT_RE = re.compile(r"(?:^|\s)-c\s+statement_timeout=\S+")


def _append_statement_timeout(options: str, timeout_ms: int) -> str:
    cleaned = _STATEMENT_TIMEOUT_RE.sub("", options or "").strip()
    snippet = f"-c statement_timeout={int(timeout_ms)}"
    if not cleaned:
        return snippet
    return f"{cleaned} {snippet}"


def _apply_postgres_timeouts(url: URL, settings: DatabaseSettings) -> URL:
    query = dict(url.query or {})
    if settings.database_connect_timeout_seconds is not None:
        query["connect_timeout"] = str(int(settings.database_connect_timeout_seconds))
    if settings.database_statement_timeout_ms is not None:
        options = str(query.get("options", "")).strip()
        query["options"] = _append_statement_timeout(options, settings.database_statement_timeout_ms)
    return url.set(query=query)


def attach_azure_postgres_managed_identity(engine: Engine) -> None:
    """Inject an Azure AD access token for Azure Database for PostgreSQL."""
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )

    credential = DefaultAzureCredential()
    token_scope = DEFAULT_AZURE_PG_SCOPE

    @event.listens_for(engine, "do_connect", insert=True)
    def _inject_token(_dialect, _conn_rec, _cargs, cparams):
        cparams["password"] = credential.get_token(token_scope).token
        if "sslmode" not in cparams:
            cparams["sslmode"] = "require"


def get_azure_postgres_access_token() -> str:
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )
    credential = DefaultAzureCredential()
    token_scope = DEFAULT_AZURE_PG_SCOPE
    return credential.get_token(token_scope).token


def _create_postgres_engine(url: URL, settings: DatabaseSettings) -> Engine:
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername="postgresql+psycopg")
    if not url.drivername.startswith("postgresql+psycopg"):
        raise ValueError("For Postgres, use postgresql+psycopg://... (psycopg is required).")

    url = _apply_sslrootcert(url, settings.database_sslrootcert)
    url = _apply_postgres_timeouts(url, settings)

    engine = create_engine(
        url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )

    if settings.database_auth_mode == "managed_identity":
        attach_azure_postgres_managed_identity(engine)

    return engine


def _normalize_psycopg_url(url: URL) -> URL:
    if url.drivername in {"postgresql", "postgres"}:
        return url
    if url.drivername.startswith("postgresql+"):
        return url.set(drivername="postgresql")
    return url


def build_engine(settings: DatabaseSettings) -> Engine:
    if not settings.database_url:
        raise ValueError("Settings.database_url is required.")
    url = make_url(str(settings.database_url))
    backend = url.get_backend_name()

    if backend == "postgresql":
        return _create_postgres_engine(url, settings)
    raise ValueError("Unsupported database backend. Use postgresql+psycopg://.")


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """Standard session scope with commit/rollback."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def build_psycopg_connect_kwargs(settings: DatabaseSettings) -> dict[str, Any]:
    """Build psycopg connection kwargs from settings."""
    url = _normalize_psycopg_url(make_url(str(settings.database_url)))
    url = _apply_postgres_timeouts(url, settings)
    params: dict[str, Any] = {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "dbname": url.database,
    }
    if url.password:
        params["password"] = url.password
    params.update(url.query or {})

    if settings.database_auth_mode == "managed_identity":
        params["password"] = get_azure_postgres_access_token()
        params.setdefault("sslmode", "require")
    if settings.database_sslrootcert:
        params["sslrootcert"] = settings.database_sslrootcert

    return params


def assert_tables_exist(
    engine: Engine,
    required_tables: list[str],
    *,
    schema: str | None = None,
) -> None:
    """Raise if required tables are missing."""
    inspector = inspect(engine)
    missing = [t for t in required_tables if not inspector.has_table(t, schema=schema)]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            "Run `ade db migrate` before starting ADE services."
        )


__all__ = [
    "DatabaseSettings",
    "build_engine",
    "attach_azure_postgres_managed_identity",
    "get_azure_postgres_access_token",
    "session_scope",
    "assert_tables_exist",
    "build_psycopg_connect_kwargs",
]
