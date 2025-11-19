"""Clean and reset commands."""

from __future__ import annotations

import shutil
import sys

import typer

from ade_tools.commands import common


def run_clean(yes: bool = False) -> None:
    """Remove build artifacts and caches (virtualenv kept); skip prompts with --yes."""

    common.refresh_paths()
    targets = [
        common.BACKEND_SRC / "web" / "static",
        common.FRONTEND_DIR / "dist",
        common.REPO_ROOT / ".ruff_cache",
        common.REPO_ROOT / ".pytest_cache",
    ]

    if not yes:
        typer.echo("This will remove:")
        for target in targets:
            typer.echo(f"  - {target.relative_to(common.REPO_ROOT)}")
        confirm = typer.confirm("Proceed?", default=False)
        if not confirm:
            typer.echo("🛑 clean cancelled")
            raise typer.Exit(code=0)

    for target in targets:
        shutil.rmtree(target, ignore_errors=True)
    typer.echo("🧹 cleaned")


def run_reset(yes: bool = False) -> None:
    """Reset ADE storage under ./data and remove build artifacts (dependencies unchanged)."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    args = [sys.executable, "-m", "ade_api.scripts.reset_storage"]
    if yes:
        args.append("--yes")
    common.run(args, cwd=common.REPO_ROOT)

    run_clean(yes=True)
    typer.echo("🔁 reset complete (dependencies unchanged)")


def register(app: typer.Typer) -> None:
    @app.command(help=run_clean.__doc__)
    def clean(yes: bool = typer.Option(False, "--yes", "-y", help="Remove artifacts without prompting.")) -> None:
        run_clean(yes)

    @app.command(help=run_reset.__doc__)
    def reset(yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts.")) -> None:
        run_reset(yes)
