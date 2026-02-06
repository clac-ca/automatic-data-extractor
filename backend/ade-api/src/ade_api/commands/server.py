"""Server commands for ADE API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.commands import common
from ade_api.settings import Settings

DEFAULT_API_BIND_PORT = 8001
DEFAULT_DEV_PROCESSES = 1
DEV_RELOAD_DIRS = (
    "backend/ade-api",
    "backend/ade-db",
    "backend/ade-storage",
)


def _prepare_env() -> dict[str, str]:
    env = common.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_dev(
    *,
    host: str | None = None,
    processes: int | None = None,
) -> None:
    """Run the API dev server (uvicorn --reload)."""

    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    # Keep dev mode reload-first by default. Multi-process dev is opt-in via --processes.
    processes = int(processes if processes is not None else DEFAULT_DEV_PROCESSES)

    env = _prepare_env()
    env["ADE_API_PROCESSES"] = str(processes)
    common.uvicorn_path()

    if processes > 1:
        typer.echo("Note: API processes > 1; disabling reload in dev.")

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
    if processes == 1:
        api_cmd.append("--reload")
        for reload_dir in DEV_RELOAD_DIRS:
            api_cmd.extend(["--reload-dir", reload_dir])
    else:
        api_cmd.extend(["--workers", str(processes)])

    typer.echo(f"API dev server: http://{host}:{port}")
    common.run(api_cmd, cwd=common.REPO_ROOT, env=env)


def run_start(
    *,
    host: str | None = None,
    processes: int | None = None,
) -> None:
    """Start the API server (requires migrations to be applied)."""

    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    processes = int(processes if processes is not None else (settings.api_processes or 1))

    env = _prepare_env()
    env["ADE_API_PROCESSES"] = str(processes)

    uvicorn_bin = common.uvicorn_path()
    api_cmd = [
        uvicorn_bin,
        "ade_api.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--loop",
        "uvloop",
        "--http",
        "httptools",
        "--log-level",
        settings.effective_api_log_level.lower(),
    ]
    if settings.api_proxy_headers_enabled:
        api_cmd.append("--proxy-headers")
        api_cmd.extend(["--forwarded-allow-ips", settings.api_forwarded_allow_ips])
    else:
        api_cmd.append("--no-proxy-headers")
    if not settings.access_log_enabled:
        api_cmd.append("--no-access-log")
    if processes and processes > 1:
        api_cmd.extend(["--workers", str(processes)])

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
        processes: int = typer.Option(
            None,
            "--processes",
            help="Number of API processes (disables reload when > 1).",
            min=1,
        ),
    ) -> None:
        run_dev(host=host, processes=processes)

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
        processes: int = typer.Option(
            None,
            "--processes",
            help="Number of API processes.",
            envvar="ADE_API_PROCESSES",
            min=1,
        ),
    ) -> None:
        run_start(host=host, processes=processes)
