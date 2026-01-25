"""Worker run commands."""

from __future__ import annotations

import typer

from ade_worker.loop import main as worker_main


def run_worker() -> None:
    """Start the ADE worker process."""
    worker_main()


def register(app: typer.Typer) -> None:
    @app.command(name="start", help="Start the ADE worker process.")
    def start() -> None:
        run_worker()

    @app.command(name="dev", help="Run the worker in dev mode (same as start).")
    def dev() -> None:
        run_worker()
