"""ade-db: CLI for ADE database migrations."""

from __future__ import annotations

import typer
from alembic import command
from sqlalchemy import text

from ade_api.settings import get_settings

from .engine import build_engine
from .migrations_runner import alembic_config, run_migrations

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE database CLI (migrate, history, current, stamp, reset).",
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


@app.command(name="reset", help="Drop and recreate the public schema, then migrate.")
def reset(
    yes: bool = typer.Option(False, "--yes", help="Confirm destructive reset."),
) -> None:
    if not yes:
        typer.echo("error: reset requires --yes", err=True)
        raise typer.Exit(code=1)

    settings = get_settings()
    engine = build_engine(settings)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    run_migrations()


if __name__ == "__main__":
    app()
