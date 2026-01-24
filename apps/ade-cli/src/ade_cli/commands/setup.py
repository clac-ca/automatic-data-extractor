"""Setup command."""

from __future__ import annotations

import typer

from ade_cli.commands import common


SETUP_INSTRUCTIONS = """
ADE uses uv + a repo-local virtualenv. From the repo root:

macOS / Linux:
    uv sync --locked
    source .venv/bin/activate
    cd apps/ade-web && npm install && cd -

Windows (PowerShell):
    uv sync --locked
    .\\.venv\\Scripts\\Activate.ps1
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
