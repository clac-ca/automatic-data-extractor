"""
Azure SQL Managed Identity auth helpers for pyodbc/SQLAlchemy.

Isolated from database.py to keep the core DB setup simple.
"""

from __future__ import annotations

import struct
import threading
import time

from sqlalchemy import event
from sqlalchemy.engine import Engine

# Optional dependency (Managed Identity)
try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:
    DefaultAzureCredential = None  # type: ignore[assignment]

_AZURE_SQL_SCOPE = "https://database.windows.net/.default"
_SQL_COPT_SS_ACCESS_TOKEN = 1256  # ODBC constant for access token injection


def _strip_odbc_kv(conn_str: str, *, drop_keys: set[str]) -> str:
    """Remove ODBC connection-string keys that may conflict with token auth."""
    if not conn_str:
        return conn_str

    drop = {k.strip().lower() for k in drop_keys}
    parts = [p for p in conn_str.split(";") if p]
    kept: list[str] = []
    for part in parts:
        key = part.split("=", 1)[0].strip().lower()
        if key in drop:
            continue
        kept.append(part)
    return ";".join(kept)


def attach_azure_sql_managed_identity(engine: Engine, *, client_id: str | None) -> None:
    """
    Inject an Azure AD access token for Azure SQL via pyodbc attrs_before.
    Token is cached with a small refresh window to avoid per-connect token calls.
    """
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=sql_password."
        )

    credential = DefaultAzureCredential(managed_identity_client_id=client_id or None)

    lock = threading.Lock()
    cached_token_bytes: bytes | None = None
    cached_expires_on: int = 0
    refresh_window_seconds = 300  # refresh 5 minutes before expiry

    def _get_token_bytes() -> bytes:
        nonlocal cached_token_bytes, cached_expires_on
        now = int(time.time())

        with lock:
            if cached_token_bytes is not None and now < (cached_expires_on - refresh_window_seconds):
                return cached_token_bytes

            token = credential.get_token(_AZURE_SQL_SCOPE)
            raw = token.token.encode("utf-16-le")
            cached_token_bytes = struct.pack("<I", len(raw)) + raw
            cached_expires_on = int(getattr(token, "expires_on", now + 3600))
            return cached_token_bytes

    @event.listens_for(engine, "do_connect", insert=True)
    def _inject_token(_dialect, _conn_rec, cargs, cparams):
        # pyodbc.connect(connection_string, **cparams)
        if cargs and isinstance(cargs[0], str):
            cargs[0] = _strip_odbc_kv(
                cargs[0],
                drop_keys={
                    "Trusted_Connection",
                    "Authentication",
                    "UID",
                    "PWD",
                    "User ID",
                    "Password",
                },
            )

        attrs_before = dict(cparams.get("attrs_before") or {})
        attrs_before[_SQL_COPT_SS_ACCESS_TOKEN] = _get_token_bytes()
        cparams["attrs_before"] = attrs_before

        # Defensive cleanup
        for k in ("user", "username", "password"):
            cparams.pop(k, None)
