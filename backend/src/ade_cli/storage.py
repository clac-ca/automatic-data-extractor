"""`ade-storage` command implementations."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer

from ade_storage.factory import build_storage_adapter
from ade_storage.settings import get_settings

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE storage CLI (check, reset).",
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="check", help="Verify storage connectivity and container access.")
def check() -> None:
    settings = get_settings()
    adapter = build_storage_adapter(settings)
    adapter.check_connection()
    typer.echo("storage connection OK")


class ResetMode(str, Enum):
    PREFIX = "prefix"
    CONTAINER = "container"


@app.command(name="reset", help="Delete ADE blobs from storage (destructive).")
def reset(
    mode: Annotated[
        ResetMode,
        typer.Option(
            "--mode",
            help="Delete by prefix (default) or entire container contents.",
        ),
    ] = ResetMode.PREFIX,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm destructive reset."),
    ] = False,
) -> None:
    if not yes:
        typer.echo("error: reset requires --yes", err=True)
        raise typer.Exit(code=1)

    settings = get_settings()
    adapter = build_storage_adapter(settings)
    prefix = settings.blob_prefix if mode is ResetMode.PREFIX else None
    deleted = adapter.delete_prefix(prefix)
    typer.echo(f"deleted {deleted} blobs")


__all__ = ["app"]

