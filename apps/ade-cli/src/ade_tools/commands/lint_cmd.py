"""Lint command."""

from __future__ import annotations

import shutil
import sys

import typer

from ade_tools.commands import common


def run_lint(scope: str) -> None:
    scope_normalized = (scope or "all").lower()
    valid = {"backend", "frontend", "all"}
    if scope_normalized not in valid:
        typer.echo(f"Unknown scope '{scope_normalized}'. Use backend, frontend, or all.", err=True)
        raise typer.Exit(code=1)

    run_backend = scope_normalized in {"backend", "all"}
    run_frontend = scope_normalized in {"frontend", "all"}

    if run_backend and common.BACKEND_SRC.exists():
        common.require_python_module(
            "ruff",
            "Install backend dev dependencies (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
        )
        common.run([sys.executable, "-m", "ruff", "check", "src/ade_api"], cwd=common.BACKEND_DIR)
        mypy_bin = shutil.which("mypy")
        if mypy_bin:
            common.run([mypy_bin, "src/ade_api"], cwd=common.BACKEND_DIR)
        else:
            typer.echo("ℹ️  mypy not installed; skipping type check", err=True)

    pkg = common.load_frontend_package_json()
    if run_frontend and common.FRONTEND_DIR.exists() and "lint" in pkg.get("scripts", {}):
        npm_bin = common.npm_path()
        common.ensure_node_modules()
        common.run([npm_bin, "run", "lint"], cwd=common.FRONTEND_DIR)

    typer.echo("✅ lint complete")


def lint_command(scope: str = "all") -> None:
    """Run backend ruff/mypy and frontend eslint; scope with --scope backend|frontend|all."""

    run_lint(scope)


def register(app: typer.Typer) -> None:
    @app.command(help=lint_command.__doc__)
    def lint(
        scope: str = typer.Option(
            "all",
            "--scope",
            "-s",
            help="Which linters to run: backend, frontend, or all.",
        ),
    ) -> None:
        lint_command(scope)
