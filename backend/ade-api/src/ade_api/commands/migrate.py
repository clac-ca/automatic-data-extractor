"""Database migration command for ADE API."""

from __future__ import annotations

import typer

from ade_api.db.migrations import run_migrations


def run_migrate(revision: str = "head") -> None:
    """Run Alembic migrations (default upgrade to head)."""
    run_migrations(revision=revision)


def register(app: typer.Typer) -> None:
    @app.command(name="migrate", help=run_migrate.__doc__)
    def migrate(
        revision: str = typer.Argument("head", help="Alembic revision to upgrade to."),
    ) -> None:
        run_migrate(revision)
