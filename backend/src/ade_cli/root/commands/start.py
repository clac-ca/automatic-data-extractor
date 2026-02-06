"""`ade start` command."""

from __future__ import annotations

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="start", help="Start API + worker + web (default).")
    def start(
        services: str | None = typer.Option(
            None,
            "--services",
            help="Comma-separated services to run (api,worker,web).",
            envvar="ADE_SERVICES",
        ),
        migrate: bool = typer.Option(
            True,
            "--migrate/--no-migrate",
            help="Run database migrations before starting services.",
            envvar="ADE_DB_MIGRATE_ON_START",
        ),
    ) -> None:
        shared._run_root_mode(mode="start", services=services, migrate=migrate)
