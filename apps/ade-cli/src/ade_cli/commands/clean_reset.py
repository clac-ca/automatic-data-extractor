"""Clean and reset commands."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer

from ade_cli.commands import common


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            return


def _remove_named_dirs(root: Path, names: set[str]) -> None:
    for path in root.rglob("*"):
        if path.is_dir() and path.name in names:
            shutil.rmtree(path, ignore_errors=True)


def _remove_suffix_dirs(root: Path, suffixes: set[str]) -> None:
    for path in root.rglob("*"):
        if path.is_dir() and any(path.name.endswith(suffix) for suffix in suffixes):
            shutil.rmtree(path, ignore_errors=True)


def _remove_named_files(root: Path, patterns: set[str]) -> None:
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file():
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue


def run_clean(yes: bool = False, *, all_deps: bool = False) -> None:
    """Remove build artifacts and caches (dependencies kept); add --all to drop node_modules."""

    common.refresh_paths()
    repo_root = common.REPO_ROOT
    explicit_targets = [
        common.BACKEND_SRC / "web" / "static",
        common.FRONTEND_DIR / "dist",
        repo_root / "dist",
        repo_root / "build",
        repo_root / ".ruff_cache",
        repo_root / ".pytest_cache",
        repo_root / ".mypy_cache",
        repo_root / ".coverage",
        repo_root / "coverage.xml",
        repo_root / "htmlcov",
    ]
    cache_dir_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    cache_dir_suffixes = {".egg-info"}
    cache_file_patterns = {"*.pyc", "*.pyo"}
    extra_targets = [common.FRONTEND_DIR / "node_modules"] if all_deps else []

    if not yes:
        typer.echo("This will remove:")
        for target in explicit_targets:
            typer.echo(f"  - {target.relative_to(repo_root)}")
        typer.echo(f"  - **/{'|'.join(sorted(cache_dir_names))} (all locations)")
        typer.echo("  - **/*.egg-info (all locations)")
        typer.echo(f"  - **/{'|'.join(sorted(cache_file_patterns))} (all locations)")
        if extra_targets:
            for target in extra_targets:
                typer.echo(f"  - {target.relative_to(repo_root)}")
        confirm = typer.confirm("Proceed?", default=False)
        if not confirm:
            typer.echo("🛑 clean cancelled")
            raise typer.Exit(code=0)

    for target in explicit_targets:
        _remove_path(target)
    _remove_named_dirs(repo_root, cache_dir_names)
    _remove_suffix_dirs(repo_root, cache_dir_suffixes)
    _remove_named_files(repo_root, cache_file_patterns)
    for target in extra_targets:
        _remove_path(target)
    typer.echo("🧹 cleaned")


def run_reset(yes: bool = False, *, dry_run: bool = False) -> None:
    """Drop ADE database tables, reset storage (filesystem/blob), and remove build artifacts (dependencies unchanged)."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE dependencies (run `bash scripts/dev/bootstrap.sh`).",
    )
    args = [sys.executable, "-m", "ade_api.scripts.reset_storage"]
    if yes:
        args.append("--yes")
    if dry_run:
        args.append("--dry-run")
    common.run(args, cwd=common.REPO_ROOT)

    if dry_run:
        typer.echo("🧪 reset dry run complete (no changes applied)")
        return

    run_clean(yes=True)
    typer.echo("🔁 reset complete (dependencies unchanged)")


def register(app: typer.Typer) -> None:
    @app.command(help=run_clean.__doc__)
    def clean(
        yes: bool = typer.Option(False, "--yes", "-y", help="Remove artifacts without prompting."),
        all_deps: bool = typer.Option(
            False,
            "--all",
            help="Also remove frontend dependencies (apps/ade-web/node_modules).",
        ),
    ) -> None:
        run_clean(yes, all_deps=all_deps)

    @app.command(help=run_reset.__doc__)
    def reset(
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed."),
    ) -> None:
        run_reset(yes, dry_run=dry_run)
