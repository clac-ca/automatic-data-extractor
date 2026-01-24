"""Lint command."""

from __future__ import annotations

import re
import shutil
import sys

import typer

from ade_cli.commands import common


def run_lint(scope: str, fix: bool = False) -> None:
    common.refresh_paths()
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
            "Install backend dev dependencies (run `bash scripts/dev/bootstrap.sh`).",
        )
        ruff_cmd = [sys.executable, "-m", "ruff", "check"]
        if fix:
            ruff_cmd.append("--fix")
        ruff_cmd.append("src/ade_api")
        common.run(ruff_cmd, cwd=common.BACKEND_DIR)
        mypy_bin = shutil.which("mypy")
        if mypy_bin:
            # mypy rejects package paths that include characters outside [a-zA-Z0-9_],
            # which is common for hyphenated repo directories. Skip gracefully to avoid
            # false-negative failures when the checkout path is not a valid module name.
            invalid_segments = [
                part
                for part in common.BACKEND_DIR.resolve().parts
                if part not in {"/"} and not re.fullmatch(r"[A-Za-z0-9_]+", part)
            ]
            if invalid_segments:
                typer.echo(
                    f"ℹ️  Skipping mypy because path contains invalid package segments: {', '.join(invalid_segments)}",
                    err=True,
                )
            else:
                common.run([mypy_bin, "src/ade_api"], cwd=common.BACKEND_DIR)
        else:
            typer.echo("ℹ️  mypy not installed; skipping type check", err=True)

    pkg = common.load_frontend_package_json()
    if run_frontend and common.FRONTEND_DIR.exists() and "lint" in pkg.get("scripts", {}):
        npm_bin = common.npm_path()
        common.ensure_node_modules()
        lint_cmd = [npm_bin, "run", "lint"]
        if fix:
            lint_cmd.extend(["--", "--fix"])
        common.run(lint_cmd, cwd=common.FRONTEND_DIR)

    typer.echo("✅ lint complete")


def lint_command(scope: str = "all", fix: bool = False) -> None:
    """Run backend ruff/mypy and frontend eslint; scope with --scope backend|frontend|all (use --fix to auto-apply)."""

    run_lint(scope, fix)


def register(app: typer.Typer) -> None:
    @app.command(help=lint_command.__doc__)
    def lint(
        scope: str = typer.Option(
            "all",
            "--scope",
            "-s",
            help="Which linters to run: backend, frontend, or all.",
        ),
        fix: bool = typer.Option(
            False,
            "--fix",
            help="Auto-apply lint fixes where supported (ruff/eslint).",
        ),
    ) -> None:
        lint_command(scope, fix)
