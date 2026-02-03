"""ade-db: CLI for ADE database migrations."""

from __future__ import annotations

import typer
from alembic import command

from .migrations_runner import alembic_config, run_migrations

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE database CLI (migrate, history, current, stamp).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="migrate", help="Apply Alembic migrations (upgrade head).")
def migrate(
    revision: str = typer.Argument("head", help="Alembic revision to upgrade to."),
) -> None:
    run_migrations(revision=revision)


@app.command(name="history", help="Show migration history.")
def history(
    rev_range: str | None = typer.Argument(None, help="Revision range (optional)."),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
) -> None:
    with alembic_config() as cfg:
        command.history(cfg, rev_range, verbose=verbose)


@app.command(name="current", help="Show current database revision.")
def current(
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
) -> None:
    with alembic_config() as cfg:
        command.current(cfg, verbose=verbose)


@app.command(name="stamp", help="Stamp revision without running migrations.")
def stamp(
    revision: str = typer.Argument(..., help="Alembic revision to stamp."),
) -> None:
    with alembic_config() as cfg:
        command.stamp(cfg, revision)


if __name__ == "__main__":
    app()
