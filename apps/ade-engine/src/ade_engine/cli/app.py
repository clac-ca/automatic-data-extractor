"""CLI entrypoint for :mod:`ade_engine`.

Exposes the ADE engine CLI with:

- `process` - normalize inputs (subcommands: `file`, `batch`).
- `config`  - create and validate config packages (subcommands: `init`, `validate`).
- `version` - print the engine version.
"""

from __future__ import annotations

import typer

from ade_engine import __version__
from ade_engine.cli.config import app as config_app
from ade_engine.cli.process import app as process_app


app = typer.Typer(
    help=(
        "ADE Engine — Automatic Data Extraction CLI.\n\n"
        "Process documents and directories using ADE's extraction engine, and manage config packages.\n\n"
        "## Quick Start Workflow\n\n"
        "### 1. Create a new config package\n"
        "```bash\n"
        "ade-engine config init my-config --package-name ade_config\n"
        "```\n\n"
        "### 2. Validate the config package\n"
        "```bash\n"
        "ade-engine config validate --config-package my-config\n"
        "```\n\n"
        "### 3. Process a single file\n"
        "```bash\n"
        "ade-engine process file \\\n"
        "    --input invoice.xlsx \\\n"
        "    --output extracted/invoice.xlsx \\\n"
        "    --config-package my-config\n"
        "```\n\n"
        "### 4. Process an entire directory\n"
        "```bash\n"
        "ade-engine process batch \\\n"
        "    --input-dir incoming/ \\\n"
        "    --output-dir extracted/ \\\n"
        "    --config-package my-config\n"
        "```\n"
    ),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

# Subcommand groups
app.add_typer(process_app, name="process")
app.add_typer(config_app, name="config")


@app.command("version")
def version_command() -> None:
    """Print the engine version."""
    typer.echo(__version__)


def main() -> None:
    """Entrypoint used by console scripts and `python -m ade_engine`."""
    app()


__all__ = ["app", "main"]
