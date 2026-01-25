"""ade-worker: CLI for ADE worker."""

from __future__ import annotations

import typer

from ade_worker.commands import register_all

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE worker CLI (start, dev, tests, lint).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


register_all(app)


if __name__ == "__main__":
    app()
