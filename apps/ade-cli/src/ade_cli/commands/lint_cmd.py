"""Lint command."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import typer

from ade_cli.commands import common


def _run_ruff(path: str, *, cwd: Path, fix: bool) -> None:
    common.require_python_module(
        "ruff",
        "Install backend dev dependencies (run `bash scripts/dev/bootstrap.sh`).",
    )
    ruff_cmd = [sys.executable, "-m", "ruff", "check"]
    if fix:
        ruff_cmd.append("--fix")
    ruff_cmd.append(path)
    common.run(ruff_cmd, cwd=cwd)


def _run_api_lint(fix: bool) -> None:
    if not common.BACKEND_SRC.exists():
        typer.echo("⚠️  API source directory not found; skipping.", err=True)
        return

    _run_ruff("src/ade_api", cwd=common.BACKEND_DIR, fix=fix)

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
                "ℹ️  Skipping mypy because path contains invalid package segments: "
                f"{', '.join(invalid_segments)}",
                err=True,
            )
        else:
            common.run([mypy_bin, "src/ade_api"], cwd=common.BACKEND_DIR)
    else:
        typer.echo("ℹ️  mypy not installed; skipping type check", err=True)


def _run_worker_lint(fix: bool) -> None:
    worker_dir = common.REPO_ROOT / "apps" / "ade-worker"
    worker_src = worker_dir / "src" / "ade_worker"
    if not worker_src.exists():
        typer.echo("⚠️  Worker source directory not found; skipping.", err=True)
        return
    _run_ruff("src/ade_worker", cwd=worker_dir, fix=fix)


def _run_cli_lint(fix: bool) -> None:
    if not common.CLI_SRC.exists():
        typer.echo("⚠️  CLI source directory not found; skipping.", err=True)
        return
    _run_ruff("src/ade_cli", cwd=common.CLI_DIR, fix=fix)


def run_lint(scope: str, fix: bool = False) -> None:
    common.refresh_paths()
    scope_normalized = (scope or "all").lower()
    valid = {"backend", "api", "frontend", "web", "worker", "cli", "all"}
    if scope_normalized not in valid:
        typer.echo(
            f"Unknown scope '{scope_normalized}'. "
            "Use backend/api, frontend/web, worker, cli, or all.",
            err=True,
        )
        raise typer.Exit(code=1)

    run_api = scope_normalized in {"backend", "api", "all"}
    run_frontend = scope_normalized in {"frontend", "web", "all"}
    run_worker = scope_normalized == "worker"
    run_cli = scope_normalized == "cli"

    if run_api:
        _run_api_lint(fix)
    if run_worker:
        _run_worker_lint(fix)
    if run_cli:
        _run_cli_lint(fix)

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
    """Run ruff/mypy (API) and eslint (web); scope with --scope backend|api|frontend|web|worker|cli|all."""

    run_lint(scope, fix)


def register(app: typer.Typer) -> None:
    @app.command(help=lint_command.__doc__)
    def lint(
        scope: str = typer.Option(
            "all",
            "--scope",
            "-s",
            help="Which linters to run: backend/api, frontend/web, worker, cli, or all.",
        ),
        fix: bool = typer.Option(
            False,
            "--fix",
            help="Auto-apply lint fixes where supported (ruff/eslint).",
        ),
    ) -> None:
        lint_command(scope, fix)
