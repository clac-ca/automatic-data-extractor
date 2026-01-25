"""Lint command for ADE worker."""

from __future__ import annotations

import sys

import typer

from ade_worker.commands import common


def run_lint(fix: bool = False) -> None:
    common.require_command(
        "ruff",
        friendly_name="ruff",
        fix_hint="Install dev dependencies (run `bash scripts/dev/bootstrap.sh`).",
    )
    worker_root = common.project_root()
    cmd = [sys.executable, "-m", "ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.append("src/ade_worker")
    common.run(cmd, cwd=worker_root)


def register(app: typer.Typer) -> None:
    @app.command(name="lint", help="Run ruff on ade-worker.")
    def lint(
        fix: bool = typer.Option(False, "--fix", help="Auto-apply lint fixes where supported."),
    ) -> None:
        run_lint(fix=fix)
