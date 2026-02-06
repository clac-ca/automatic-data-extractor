"""`ade db` command."""

from __future__ import annotations

import typer

from .. import shared

_CONTEXT_SETTINGS = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "help_option_names": [],
}


def register(app: typer.Typer) -> None:
    @app.command(
        name="db",
        help="Database CLI (delegates to ade-db).",
        context_settings=_CONTEXT_SETTINGS,
    )
    def db(ctx: typer.Context) -> None:
        shared._delegate_to("ade-db", ctx)
