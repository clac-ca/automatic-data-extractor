"""`ade-api start` command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.settings import Settings

from .. import shared

DEFAULT_API_BIND_PORT = 8001


def _prepare_env() -> dict[str, str]:
    env = shared.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_start(
    *,
    host: str | None = None,
    processes: int | None = None,
) -> None:
    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    processes = int(processes if processes is not None else (settings.api_processes or 1))

    env = _prepare_env()
    env["ADE_API_PROCESSES"] = str(processes)

    uvicorn_bin = shared.uvicorn_path()
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
    shared.run(api_cmd, cwd=shared.REPO_ROOT / "backend", env=env)


def register(app: typer.Typer) -> None:
    @app.command(name="start", help="Start the API server (requires migrations).")
    def start(
        host: str | None = typer.Option(
            None,
            "--host",
            help="Host/interface for the API server.",
            envvar="ADE_API_HOST",
        ),
        processes: int | None = typer.Option(
            None,
            "--processes",
            help="Number of API processes.",
            envvar="ADE_API_PROCESSES",
            min=1,
        ),
    ) -> None:
        run_start(host=host, processes=processes)
