"""Start command."""

from __future__ import annotations

import typer

from ade_tools.commands import common


def run_start(
    port: int = 8000,
    host: str = "0.0.0.0",
    force_build: bool = False,
) -> None:
    """
    Start the backend server without autoreload.

    Ensures frontend static assets exist. If static assets are missing (or --force-build is used),
    runs the build step first using the current environment.
    """
    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e packages/ade-schemas -e apps/ade-engine -e apps/ade-api`).",
    )

    static_dir = common.BACKEND_SRC / "web" / "static"
    if force_build or not static_dir.exists():
        if force_build:
            typer.echo("ℹ️  forcing frontend build before start…")
        else:
            typer.echo("ℹ️  static assets missing; running build first…")

        # Import locally to avoid circular imports at module load time.
        from ade_tools.commands.build import run_build

        run_build()

    cmd = [
        common.uvicorn_path(),
        "ade_api.main:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
    ]

    typer.echo(f"🚀 Starting ADE backend on http://{host}:{port}")
    common.run(cmd, cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    @app.command(
        name="start",
        help="Serve backend in production mode at http://0.0.0.0:8000; auto-builds static assets if missing; use --force-build to rebuild.",
    )
    def start(
        port: int = typer.Option(
            8000,
            "--port",
            "-p",
            help="Port for the FastAPI server.",
        ),
        host: str = typer.Option(
            "0.0.0.0",
            "--host",
            help="Host/interface to bind to.",
        ),
        force_build: bool = typer.Option(
            False,
            "--force-build",
            help="Always rebuild frontend static assets before starting.",
        ),
    ) -> None:
        run_start(port=port, host=host, force_build=force_build)
