"""ade-worker: CLI for ADE worker."""

from __future__ import annotations

import typer

from .gc import run_gc
from .worker import main as worker_main

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE worker CLI (start, gc).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="start", help="Start the ADE worker process.")
def start() -> None:
    worker_main()


@app.command(name="dev", help="Run the worker in dev mode (same as start).")
def dev() -> None:
    worker_main()


@app.command(name="gc", help="Run garbage collection once.")
def gc() -> None:
    run_gc()


if __name__ == "__main__":
    app()
