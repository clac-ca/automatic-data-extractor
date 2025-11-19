"""ade: Python orchestration CLI for ADE."""

from __future__ import annotations

import typer

from ade_tools.commands import register_all

app = typer.Typer(add_completion=False, help="ADE orchestration CLI (backend + frontend).")

register_all(app)


if __name__ == "__main__":
    app()
