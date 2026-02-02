"""Routes command for ADE API."""

from __future__ import annotations

import sys

import typer

from ade_api.commands import common


def run_routes() -> None:
    """List FastAPI routes."""
    common.run([sys.executable, "-m", "ade_api.scripts.api_routes"], cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    @app.command(name="routes", help=run_routes.__doc__)
    def routes() -> None:
        run_routes()
