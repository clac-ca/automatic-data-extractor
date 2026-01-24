"""Setup command."""

from __future__ import annotations

import typer

from ade_cli.commands import common


SETUP_INSTRUCTIONS = """
ADE uses uv for dependency installs. From the repo root:

macOS / Linux:
    # Optional: create/activate a venv first if you want isolation.
    # python -m venv .venv
    # source .venv/bin/activate
    bash scripts/dev/bootstrap.sh

Windows (PowerShell):
    # Optional: create/activate a venv first if you want isolation.
    # python -m venv .venv
    # .\\.venv\\Scripts\\Activate.ps1
    bash scripts/dev/bootstrap.sh

Once dependencies are installed, run `ade dev` to start backend + frontend dev servers.
"""


def run_setup() -> None:
    """Show manual install instructions (no automatic installs)."""

    common.refresh_paths()
    typer.echo(SETUP_INSTRUCTIONS.strip())


def register(app: typer.Typer) -> None:
    @app.command(help=run_setup.__doc__)
    def setup() -> None:
        run_setup()
