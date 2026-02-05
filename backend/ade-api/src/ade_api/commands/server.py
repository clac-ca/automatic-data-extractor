"""Server commands for ADE API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.commands import common
from ade_api.settings import Settings

DEFAULT_API_BIND_PORT = 8001


def _prepare_env() -> dict[str, str]:
    env = common.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_dev(
    *,
    host: str | None = None,
    workers: int | None = None,
) -> None:
    """Run the API dev server (uvicorn --reload)."""

    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    workers = int(workers if workers is not None else (settings.api_workers or 1))

    env = _prepare_env()
    common.uvicorn_path()

    if workers > 1:
        typer.echo("Note: API workers > 1; disabling reload in dev.")

    uvicorn_bin = common.uvicorn_path()
    api_cmd = [
        uvicorn_bin,
        "ade_api.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        settings.effective_api_log_level.lower(),
    ]
    if not settings.access_log_enabled:
        api_cmd.append("--no-access-log")
    if workers == 1:
        api_cmd.extend(["--reload", "--reload-dir", "backend/ade-api"])
    else:
        api_cmd.extend(["--workers", str(workers)])

    typer.echo(f"API dev server: http://{host}:{port}")
    common.run(api_cmd, cwd=common.REPO_ROOT, env=env)


def run_start(
    *,
    host: str | None = None,
    workers: int | None = None,
) -> None:
    """Start the API server (requires migrations to be applied)."""

    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    workers = int(workers if workers is not None else (settings.api_workers or 1))

    env = _prepare_env()

    uvicorn_bin = common.uvicorn_path()
    api_cmd = [
        uvicorn_bin,
        "ade_api.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        settings.effective_api_log_level.lower(),
    ]
    if not settings.access_log_enabled:
        api_cmd.append("--no-access-log")
    if workers and workers > 1:
        api_cmd.extend(["--workers", str(workers)])

    typer.echo(f"Starting ADE API on http://{host}:{port}")
    common.run(api_cmd, cwd=common.REPO_ROOT, env=env)


def register(app: typer.Typer) -> None:
    @app.command(
        name="dev",
        help="Run the API dev server only (apply migrations first).",
    )
    def dev(
        host: str = typer.Option(
            None,
            "--host",
            help="Host/interface for the API dev server.",
            envvar="ADE_API_HOST",
        ),
        workers: int = typer.Option(
            None,
            "--workers",
            help="Number of API worker processes.",
            envvar="ADE_API_WORKERS",
            min=1,
        ),
    ) -> None:
        run_dev(host=host, workers=workers)

    @app.command(
        name="start",
        help="Start the API server (requires migrations).",
    )
    def start(
        host: str = typer.Option(
            None,
            "--host",
            help="Host/interface for the API server.",
            envvar="ADE_API_HOST",
        ),
        workers: int = typer.Option(
            None,
            "--workers",
            help="Number of API worker processes.",
            envvar="ADE_API_WORKERS",
            min=1,
        ),
    ) -> None:
        run_start(host=host, workers=workers)
