"""Root ADE CLI app."""

from __future__ import annotations

import typer

from .commands import register_all

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE CLI (start, stop, restart, status, dev, test, reset, api, worker, db, storage, web).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


register_all(app)
