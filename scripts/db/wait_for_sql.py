#!/usr/bin/env python3
"""Wait for SQL Server to accept logins.

This is intentionally tiny and dependency-light. It uses `pyodbc`, which is already
required by ADE (via ade-api / ade-worker), and therefore avoids needing `sqlcmd`
or other OS packages.

Env vars (defaults match local/devcontainer defaults):
  ADE_SQL_HOST (default: sql)
  ADE_SQL_PORT (default: 1433)
  ADE_SQL_USER (default: sa)
  ADE_SQL_PASSWORD (default: YourStrong!Passw0rd)
  ADE_SQL_ENCRYPT (default: optional)  # yes|no|optional
  ADE_SQL_TRUST_SERVER_CERTIFICATE (default: yes)

Exit code:
  0 when ready, 1 on timeout.
"""

from __future__ import annotations

import os
import sys
import time

import pyodbc


def build_conn_str() -> str:
    host = os.getenv("ADE_SQL_HOST", "sql")
    port = os.getenv("ADE_SQL_PORT", "1433")
    user = os.getenv("ADE_SQL_USER", "sa")
    password = os.getenv("ADE_SQL_PASSWORD", "YourStrong!Passw0rd")
    encrypt = os.getenv("ADE_SQL_ENCRYPT", "optional")
    trust = os.getenv("ADE_SQL_TRUST_SERVER_CERTIFICATE", "yes")

    # Note: Database=master is always present and avoids requiring ADE DB creation.
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host},{port};"
        "DATABASE=master;"
        f"UID={user};PWD={password};"
        f"Encrypt={encrypt};TrustServerCertificate={trust};"
        "Connection Timeout=3;"
    )


def main() -> int:
    timeout_s = int(os.getenv("ADE_SQL_WAIT_TIMEOUT", "90"))
    start = time.time()
    conn_str = build_conn_str()

    while True:
        try:
            with pyodbc.connect(conn_str) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            print("✅ SQL Server is ready.")
            return 0
        except Exception as exc:  # noqa: BLE001
            elapsed = int(time.time() - start)
            if elapsed >= timeout_s:
                print(f"❌ Timed out waiting for SQL Server after {timeout_s}s: {exc}", file=sys.stderr)
                return 1
            print(f"⏳ Waiting for SQL Server... ({elapsed}s) {exc}")
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
