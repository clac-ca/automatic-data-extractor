"""Start command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_cli.commands import common
from ade_cli.commands.migrate import run_migrate


def run_start(
    api_port: int = 8000,
    api_host: str = "0.0.0.0",
    web: bool = True,
    worker: bool = True,
) -> None:
    """
    Start the API (no autoreload), production frontend, and the background worker.
    """
    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )
    common.uvicorn_path()
    if worker:
        common.require_python_module(
            "ade_worker",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-worker`).",
        )

    env = common.build_env()
    venv_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    if web:
        dist_env = env.get("ADE_FRONTEND_DIST_DIR")
        if dist_env:
            dist_path = Path(dist_env)
            if not dist_path.exists():
                typer.echo(
                    f"❌ frontend dist dir not found: {dist_path}. "
                    "Set ADE_FRONTEND_DIST_DIR or run `ade build`.",
                    err=True,
                )
                raise typer.Exit(code=1)
        else:
            common.ensure_frontend_dir()
            dist_dir = common.FRONTEND_DIR / "dist"
            if not dist_dir.exists():
                typer.echo("ℹ️  frontend build missing; running `ade build`…")
                from ade_cli.commands.build import run_build

                run_build()
            if not dist_dir.exists():
                typer.echo("❌ frontend build output missing; expected apps/ade-web/dist", err=True)
                raise typer.Exit(code=1)
            dist_env = str(dist_dir)
        env["ADE_FRONTEND_DIST_DIR"] = dist_env
        typer.echo(f"🧭 Frontend dist:        {dist_env}")

    typer.echo("🗄️  Running migrations…")
    run_migrate()

    uvicorn_bin = common.uvicorn_path()
    tasks: list[tuple[str, list[str], Path | None, dict[str, str]]] = [
        (
            "api",
            [
                uvicorn_bin,
                "ade_api.main:create_app",
                "--factory",
                "--host",
                api_host,
                "--port",
                str(api_port),
            ],
            common.REPO_ROOT,
            env,
        )
    ]

    if worker:
        tasks.append(
            (
                "worker",
                ["ade-worker"],
                common.REPO_ROOT,
                env,
            )
        )

    typer.echo(f"🚀 Starting ADE API on http://{api_host}:{api_port}")
    if worker:
        typer.echo("🧵 Starting ADE worker")
    common.run_parallel(tasks)


def register(app: typer.Typer) -> None:
    @app.command(
        name="start",
        help="Serve the API + production frontend + worker (runs migrations first).",
    )
    def start(
        api_port: int = typer.Option(
            8000,
            "--api-port",
            help="Port for the API server.",
        ),
        api_host: str = typer.Option(
            "0.0.0.0",
            "--api-host",
            help="Host/interface for the API server.",
        ),
        web: bool = typer.Option(
            True,
            "--web/--no-web",
            help="Serve the built frontend from this process.",
        ),
        worker: bool = typer.Option(
            True,
            "--worker/--no-worker",
            help="Run the background worker alongside the API.",
        ),
    ) -> None:
        run_start(
            api_port=api_port,
            api_host=api_host,
            web=web,
            worker=worker,
        )
