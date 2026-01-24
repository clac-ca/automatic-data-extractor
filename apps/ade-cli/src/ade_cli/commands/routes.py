"""Routes command."""

from __future__ import annotations

import sys

import typer

from ade_cli.commands import common


def run_routes() -> None:
    """List backend routes."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your uv-managed virtualenv (e.g., `uv sync --locked`).",
    )
    common.run([sys.executable, "-m", "ade_api.scripts.api_routes"], cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    @app.command(
        name="routes",
        help=run_routes.__doc__,
    )
    def routes() -> None:
        run_routes()
