"""`ade stop` command."""

from __future__ import annotations

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="stop", help="Stop tracked ADE service processes.")
    def stop(
        timeout: float = typer.Option(
            shared.DEFAULT_STOP_TIMEOUT_SECONDS,
            "--timeout",
            help="Seconds to wait after SIGTERM before force-stopping with SIGKILL.",
            min=0.0,
        ),
    ) -> None:
        shared._stop_ade_services(timeout=timeout)
