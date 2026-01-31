"""Lint command for ADE API."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import typer

from ade_api.commands import common


def run_lint(fix: bool = False) -> None:
    api_root = Path(__file__).resolve().parents[3]
    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        typer.echo("❌ ruff not found. Install dev dependencies (run `./setup.sh`).", err=True)
        raise typer.Exit(code=1)

    ruff_cmd = [sys.executable, "-m", "ruff", "check"]
    if fix:
        ruff_cmd.append("--fix")
    ruff_cmd.append("src/ade_api")
    common.run(ruff_cmd, cwd=api_root)

    mypy_bin = shutil.which("mypy")
    if mypy_bin:
        invalid_segments = [
            part
            for part in api_root.resolve().parts
            if part not in {"/"} and not re.fullmatch(r"[A-Za-z0-9_]+", part)
        ]
        if invalid_segments:
            typer.echo(
                "ℹ️  Skipping mypy because path contains invalid package segments: "
                f"{', '.join(invalid_segments)}",
                err=True,
            )
        else:
            common.run([mypy_bin, "src/ade_api"], cwd=api_root)
    else:
        typer.echo("ℹ️  mypy not installed; skipping type check", err=True)


def register(app: typer.Typer) -> None:
    @app.command(name="lint", help="Run ruff/mypy on ade-api.")
    def lint(
        fix: bool = typer.Option(False, "--fix", help="Auto-apply lint fixes where supported."),
    ) -> None:
        run_lint(fix=fix)
