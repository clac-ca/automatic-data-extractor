"""`ade-api dev` command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.settings import Settings

from .. import shared

DEFAULT_API_BIND_PORT = 8001
DEFAULT_DEV_PROCESSES = 1
DEV_RELOAD_DIRS = (
    "src",
    "tests/api",
    "tests/worker",
)


def _prepare_env() -> dict[str, str]:
    env = shared.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_dev(
    *,
    host: str | None = None,
    processes: int | None = None,
) -> None:
    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    processes = int(processes if processes is not None else DEFAULT_DEV_PROCESSES)

    env = _prepare_env()
    env["ADE_API_PROCESSES"] = str(processes)

    if processes > 1:
        typer.echo("Note: API processes > 1; disabling reload in dev.")

    uvicorn_bin = shared.uvicorn_path()
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
    shared.run(api_cmd, cwd=shared.REPO_ROOT / "backend", env=env)


def register(app: typer.Typer) -> None:
    @app.command(name="dev", help="Run the API dev server only (apply migrations first).")
    def dev(
        host: str | None = typer.Option(
            None,
            "--host",
            help="Host/interface for the API dev server.",
            envvar="ADE_API_HOST",
        ),
        processes: int | None = typer.Option(
            None,
            "--processes",
            help="Number of API processes (disables reload when > 1).",
            min=1,
        ),
    ) -> None:
        run_dev(host=host, processes=processes)
