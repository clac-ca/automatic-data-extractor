"""Worker command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_cli.commands import common


def run_worker() -> None:
    """Start the ADE worker process."""
    common.refresh_paths()
    common.require_python_module(
        "ade_worker",
        "Install ADE dependencies (run `bash scripts/dev/bootstrap.sh`).",
    )

    env = common.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"

    typer.echo("🧵 Starting ADE worker…")
    common.run(["ade-worker"], cwd=common.REPO_ROOT, env=env)


def register(app: typer.Typer) -> None:
    @app.command(name="worker", help=run_worker.__doc__)
    def worker() -> None:
        run_worker()
