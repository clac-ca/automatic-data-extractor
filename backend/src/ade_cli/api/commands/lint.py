"""Lint command for ADE API."""

from __future__ import annotations

import re
import shutil
import sys

import typer

from .. import shared


def run_lint(fix: bool = False) -> None:
    api_root = shared.REPO_ROOT / "backend"
    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        typer.echo(
            "error: ruff not found (install dependencies via `./setup.sh`).",
            err=True,
        )
        raise typer.Exit(code=1)

    ruff_cmd = [sys.executable, "-m", "ruff", "check"]
    if fix:
        ruff_cmd.append("--fix")
    ruff_cmd.append("src/ade_api")
    shared.run(ruff_cmd, cwd=api_root)

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
            shared.run([mypy_bin, "src/ade_api"], cwd=api_root)
    else:
        typer.echo("ℹ️  mypy not installed; skipping type check", err=True)


def register(app: typer.Typer) -> None:
    @app.command(name="lint", help="Run ruff/mypy on ade-api.")
    def lint(
        fix: bool = typer.Option(False, "--fix", help="Auto-apply lint fixes where supported."),
    ) -> None:
        run_lint(fix=fix)
