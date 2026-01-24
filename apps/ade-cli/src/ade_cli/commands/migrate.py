"""Migrate command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from sqlalchemy.engine import URL, make_url

from ade_cli.commands import common


def _ensure_sqlite_parent_dir(url: str) -> None:
    try:
        parsed = make_url(url)
    except Exception:
        return
    if parsed.get_backend_name() != "sqlite":
        return
    db = (parsed.database or "").strip()
    if not db or db == ":memory:" or db.startswith("file:"):
        return
    path = Path(db)
    if not path.is_absolute():
        path = (common.REPO_ROOT / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def run_migrate(revision: str = "head") -> None:
    """Run Alembic migrations (default upgrade to head) using apps/ade-api/alembic.ini."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "alembic",
        "Install backend dependencies (run `bash scripts/dev/bootstrap.sh`).",
    )
    alembic_ini = common.BACKEND_DIR / "alembic.ini"
    env = common.build_env()

    db_url = env.get("ALEMBIC_DATABASE_URL") or env.get("ADE_DATABASE_URL_OVERRIDE")
    if not db_url:
        host = env.get("ADE_SQL_HOST", "sql")
        port = int(env.get("ADE_SQL_PORT", "1433"))
        user = env.get("ADE_SQL_USER", "sa")
        password = env.get("ADE_SQL_PASSWORD", "YourStrong!Passw0rd")
        database = env.get("ADE_SQL_DATABASE", "ade")
        encrypt = env.get("ADE_SQL_ENCRYPT", "optional")
        trust_cert = env.get("ADE_SQL_TRUST_SERVER_CERTIFICATE", "yes")
        auth_mode = (env.get("ADE_DATABASE_AUTH_MODE") or "sql_password").strip().lower()

        query = {
            "driver": "ODBC Driver 18 for SQL Server",
            "Encrypt": encrypt,
            "TrustServerCertificate": trust_cert,
        }

        if auth_mode == "managed_identity":
            url = URL.create(
                drivername="mssql+pyodbc",
                username=None,
                password=None,
                host=host,
                port=port,
                database=database,
                query=query,
            )
        else:
            url = URL.create(
                drivername="mssql+pyodbc",
                username=user,
                password=password,
                host=host,
                port=port,
                database=database,
                query=query,
            )
        db_url = url.render_as_string(hide_password=False)

    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        raw_path = db_url[len("sqlite:///") :]
        if raw_path and not Path(raw_path).is_absolute():
            abs_path = (common.REPO_ROOT / raw_path).resolve()
            db_url = f"sqlite:///{abs_path.as_posix()}"

    env["ALEMBIC_DATABASE_URL"] = db_url

    _ensure_sqlite_parent_dir(db_url)

    common.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", revision],
        cwd=common.BACKEND_DIR,
        env=env,
    )


def register(app: typer.Typer) -> None:
    @app.command(help=run_migrate.__doc__)
    def migrate(
        revision: str = typer.Argument("head", help="Alembic revision to upgrade to."),
    ) -> None:
        run_migrate(revision)
