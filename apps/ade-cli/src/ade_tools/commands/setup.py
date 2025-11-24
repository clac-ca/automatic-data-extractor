"""Setup command."""

from __future__ import annotations

import typer

from ade_tools.commands import common


SETUP_INSTRUCTIONS = """
ADE uses a user-managed virtualenv. From the repo root:

macOS / Linux:
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -U pip
    pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api
    cd apps/ade-web && npm install && cd -

Windows (PowerShell):
    python -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    pip install -U pip
    pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api
    cd apps/ade-web
    npm install
    cd ..

Once dependencies are installed, run `ade dev` to start backend + frontend dev servers.
"""


def run_setup() -> None:
    """Show manual venv + editable install instructions (no automatic installs)."""

    common.refresh_paths()
    typer.echo(SETUP_INSTRUCTIONS.strip())


def register(app: typer.Typer) -> None:
    @app.command(help=run_setup.__doc__)
    def setup() -> None:
        run_setup()
