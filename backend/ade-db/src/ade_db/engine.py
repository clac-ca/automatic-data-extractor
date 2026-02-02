"""Shared database engine helpers (Postgres only)."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url

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


def _apply_sslrootcert(url: URL, sslrootcert: str | None) -> URL:
    if not sslrootcert:
        return url
    query = dict(url.query or {})
    query["sslrootcert"] = sslrootcert
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


def build_engine(settings: DatabaseSettings) -> Engine:
    if not settings.database_url:
        raise ValueError("Settings.database_url is required.")
    url = make_url(str(settings.database_url))
    backend = url.get_backend_name()

    if backend == "postgresql":
        return _create_postgres_engine(url, settings)
    raise ValueError("Unsupported database backend. Use postgresql+psycopg://.")


def build_engine_from_url(
    database_url: str | URL,
    *,
    database_echo: bool = False,
    database_auth_mode: str = "password",
    database_sslrootcert: str | None = None,
    database_pool_size: int = 5,
    database_max_overflow: int = 10,
    database_pool_timeout: int = 30,
    database_pool_recycle: int = 1800,
) -> Engine:
    class _Settings:
        def __init__(self):
            self.database_url = database_url
            self.database_echo = database_echo
            self.database_auth_mode = database_auth_mode
            self.database_sslrootcert = database_sslrootcert
            self.database_pool_size = database_pool_size
            self.database_max_overflow = database_max_overflow
            self.database_pool_timeout = database_pool_timeout
            self.database_pool_recycle = database_pool_recycle

    return build_engine(_Settings())


__all__ = [
    "DatabaseSettings",
    "build_engine",
    "build_engine_from_url",
    "attach_azure_postgres_managed_identity",
    "get_azure_postgres_access_token",
]
