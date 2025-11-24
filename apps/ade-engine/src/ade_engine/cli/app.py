"""Typer application wiring."""

from __future__ import annotations

import typer

from ade_engine.cli.commands.run import run_command
from ade_engine.cli.commands.version import version_command

app = typer.Typer(add_completion=False, help="ADE engine runtime CLI")

app.command("run")(run_command)
app.command("version")(version_command)


def main() -> None:  # pragma: no cover - exercised via CLI integration tests
    app()


__all__ = ["app", "main"]
