"""Build command."""

from __future__ import annotations

import typer

from ade_cli.commands import common


def run_build() -> None:
    """Build the web app (outputs to apps/ade-web/dist)."""

    common.refresh_paths()
    common.ensure_frontend_dir()
    dist_dir = common.FRONTEND_DIR / "dist"

    npm_bin = common.npm_path()
    common.ensure_node_modules()
    common.run([npm_bin, "run", "build"], cwd=common.FRONTEND_DIR)

    if not dist_dir.exists():
        typer.echo(f"❌ build output missing: expected {dist_dir.relative_to(common.REPO_ROOT)}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"✅ build complete: {dist_dir.relative_to(common.REPO_ROOT)}")


def register(app: typer.Typer) -> None:
    @app.command("build", help=run_build.__doc__)
    def build() -> None:
        run_build()
