"""Routes command."""

from __future__ import annotations

import sys

import typer

from ade_tools.commands import common


def routes_command() -> None:
    """List backend routes."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    common.run([sys.executable, "-m", "ade_api.scripts.api_routes"], cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    app.command()(routes_command)
