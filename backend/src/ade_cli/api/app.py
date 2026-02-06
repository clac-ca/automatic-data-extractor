"""ADE API CLI app."""

from __future__ import annotations

import typer

from .commands import register_all

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE API CLI (dev, start, test, lint, routes, types, users).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


register_all(app)
