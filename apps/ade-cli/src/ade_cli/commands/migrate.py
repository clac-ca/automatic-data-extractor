"""Migrate command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from sqlalchemy.engine import make_url

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
        "Install backend dependencies (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    alembic_ini = common.BACKEND_DIR / "alembic.ini"
    env = common.build_env()
    if "ALEMBIC_DATABASE_URL" in env:
        db_url = env["ALEMBIC_DATABASE_URL"]
    else:
        db_url = env.get("ADE_DATABASE_URL")
        if not db_url:
            default_path = (common.REPO_ROOT / "data" / "db" / "ade.sqlite").resolve()
            db_url = f"sqlite:///{default_path.as_posix()}"
        elif db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
            raw_path = db_url[len("sqlite:///"):]
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
