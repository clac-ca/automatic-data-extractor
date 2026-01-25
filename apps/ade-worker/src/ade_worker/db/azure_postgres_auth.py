"""
Azure Postgres Managed Identity auth helpers for psycopg/SQLAlchemy.

Token is injected as the password on connect.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine

# Optional dependency (Managed Identity)
try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:
    DefaultAzureCredential = None  # type: ignore[assignment]

DEFAULT_AZURE_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def attach_azure_postgres_managed_identity(engine: Engine) -> None:
    """
    Inject an Azure AD access token for Azure Database for PostgreSQL.
    """
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
    """Return an Azure AD access token for Postgres password injection."""
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )
    credential = DefaultAzureCredential()
    token_scope = DEFAULT_AZURE_PG_SCOPE
    return credential.get_token(token_scope).token


__all__ = [
    "DEFAULT_AZURE_PG_SCOPE",
    "attach_azure_postgres_managed_identity",
    "get_azure_postgres_access_token",
]
