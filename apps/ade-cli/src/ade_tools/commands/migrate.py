"""Migrate command."""

from __future__ import annotations

import sys

import typer

from ade_tools.commands import common


def run_migrate(revision: str = "head") -> None:
    """Run Alembic migrations (default upgrade to head) using apps/ade-api/alembic.ini."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "alembic",
        "Install backend dependencies (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    alembic_ini = common.BACKEND_DIR / "alembic.ini"
    common.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", revision],
        cwd=common.BACKEND_DIR,
    )


def register(app: typer.Typer) -> None:
    @app.command(help=run_migrate.__doc__)
    def migrate(
        revision: str = typer.Argument("head", help="Alembic revision to upgrade to."),
    ) -> None:
        run_migrate(revision)
