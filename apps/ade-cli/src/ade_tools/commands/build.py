"""Build command."""

from __future__ import annotations

import shutil

import typer

from ade_tools.commands import common


def run_build() -> None:
    """Build the frontend and copy static assets into the backend."""

    common.refresh_paths()
    common.ensure_frontend_dir()
    dist_dir = common.FRONTEND_DIR / "dist"
    target = common.BACKEND_SRC / "web" / "static"

    npm_bin = common.npm_path()
    common.ensure_node_modules()
    common.run([npm_bin, "run", "build"], cwd=common.FRONTEND_DIR)

    if dist_dir.exists():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(dist_dir, target)
        typer.echo(f"📦 copied {dist_dir.relative_to(common.REPO_ROOT)} → {target.relative_to(common.REPO_ROOT)}")

    typer.echo("✅ build complete")


def register(app: typer.Typer) -> None:
    @app.command("build", help=run_build.__doc__)
    def build() -> None:
        run_build()
