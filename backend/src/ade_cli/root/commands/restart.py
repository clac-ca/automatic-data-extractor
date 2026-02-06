"""`ade restart` command."""

from __future__ import annotations

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="restart", help="Stop ADE services, then start them again.")
    def restart(
        services: str | None = typer.Option(
            None,
            "--services",
            help="Comma-separated services to run after restart (api,worker,web).",
            envvar="ADE_SERVICES",
        ),
        migrate: bool = typer.Option(
            True,
            "--migrate/--no-migrate",
            help="Run database migrations before starting services.",
            envvar="ADE_DB_MIGRATE_ON_START",
        ),
        timeout: float = typer.Option(
            shared.DEFAULT_STOP_TIMEOUT_SECONDS,
            "--timeout",
            help="Seconds to wait during stop before force-stopping with SIGKILL.",
            min=0.0,
        ),
    ) -> None:
        shared._stop_ade_services(timeout=timeout)
        shared._run_root_mode(mode="start", services=services, migrate=migrate)
