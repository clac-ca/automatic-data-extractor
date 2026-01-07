"""Dev command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_cli.commands import common
from ade_cli.commands.migrate import run_migrate


def _resolve_vite_log_level(env: dict[str, str]) -> str | None:
    raw = (
        env.get("VITE_LOG_LEVEL")
        or env.get("ADE_WEB_LOG_LEVEL")
        or env.get("ADE_LOG_LEVEL")
    )
    if not raw:
        return None
    value = raw.strip().lower()
    mapping = {
        "debug": "info",
        "info": "info",
        "warn": "warn",
        "warning": "warn",
        "error": "error",
        "critical": "error",
        "fatal": "error",
        "silent": "silent",
        "none": "silent",
        "off": "silent",
    }
    return mapping.get(value, "info")


def run_dev(
    api: bool = True,
    web: bool = True,
    worker: bool = True,
    api_only: bool = False,
    web_only: bool = False,
    api_port: int | None = None,
    api_host: str | None = None,
    web_port: int | None = None,
    web_host: str | None = None,
) -> None:
    """
    Run ADE dev services with sensible defaults.

    By default runs:
      - API (FastAPI + uvicorn --reload) → http://localhost:8000
      - Web (Vite dev server)           → http://localhost:5173
      - Worker (ade-worker)

    Runs `ade migrate` automatically when the API or worker is selected.
    """
    common.refresh_paths()

    # Resolve selection flags
    if api_only and web_only:
        typer.echo("❌ Cannot use --api-only and --web-only together.", err=True)
        raise typer.Exit(code=1)

    if api_only:
        api, web, worker = True, False, False
    elif web_only:
        api, web, worker = False, True, False

    if not api and not web and not worker:
        typer.echo("⚠️ No services selected; nothing to run.", err=True)
        raise typer.Exit(code=1)

    api_port = int(api_port if api_port is not None else os.getenv("ADE_API_PORT", "8000") or "8000")
    api_host = api_host or os.getenv("ADE_API_HOST", "127.0.0.1")
    web_port = int(web_port if web_port is not None else os.getenv("ADE_WEB_PORT", "5173") or "5173")
    web_host = web_host or os.getenv("ADE_WEB_HOST", "127.0.0.1")

    api_present = common.BACKEND_SRC.exists()
    web_present = common.FRONTEND_DIR.exists()
    worker_present = (common.REPO_ROOT / "apps" / "ade-worker").exists()

    # Soften failures: skip missing pieces instead of just dying
    if api and not api_present:
        typer.echo("⚠️ API source directory not found; skipping API.", err=True)
        api = False

    if web and not web_present:
        typer.echo("⚠️ Web directory not found; skipping web.", err=True)
        web = False

    if worker and not worker_present:
        typer.echo("⚠️ Worker directory not found; skipping worker.", err=True)
        worker = False

    if not api and not web and not worker:
        typer.echo("Nothing to run yet. Add apps/ade-api/, apps/ade-web/, and/or apps/ade-worker first.")
        raise typer.Exit(code=0)

    web_pkg_path = common.FRONTEND_DIR / "package.json"
    if web and not web_pkg_path.exists():
        typer.echo("⚠️  web package.json not found; skipping web.", err=True)
        web = False

    if api and web and api_port == web_port:
        typer.echo("❌ API and web ports must be different when running both servers.", err=True)
        raise typer.Exit(code=1)

    if api:
        common.require_python_module(
            "ade_api",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
        )
        common.uvicorn_path()
        typer.echo(f"🔧 API dev server:        http://{api_host}:{api_port}")

    if web:
        common.npm_path()
        common.ensure_node_modules()
        typer.echo(f"💻 Web dev server:        http://{web_host}:{web_port}")

    if worker:
        common.require_python_module(
            "ade_worker",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-worker`).",
        )
        typer.echo("🧵 Worker:               ade-worker")

    if api or worker:
        typer.echo("🗄️  Running migrations…")
        run_migrate()

    env = common.build_env()
    venv_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    tasks: list[tuple[str, list[str], Path | None, dict[str, str]]] = []
    if api:
        uvicorn_bin = common.uvicorn_path()
        tasks.append(
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
                    "--reload",
                    "--reload-dir",
                    "apps/ade-api",
                ],
                common.REPO_ROOT,
                env,
            )
        )

    if web:
        npm_bin = common.npm_path()
        web_env = env.copy()
        if api and "VITE_API_BASE_URL" not in web_env:
            web_env["VITE_API_BASE_URL"] = f"http://localhost:{api_port}"
        web_log_level = _resolve_vite_log_level(web_env)
        if web_log_level and "VITE_LOG_LEVEL" not in web_env:
            web_env["VITE_LOG_LEVEL"] = web_log_level
        tasks.append(
            (
                "web",
                [
                    npm_bin,
                    "--prefix",
                    "apps/ade-web",
                    "run",
                    "dev",
                    "--",
                    "--host",
                    web_host,
                    "--port",
                    str(web_port),
                    *(
                        ["--logLevel", web_log_level]
                        if web_log_level is not None
                        else []
                    ),
                ],
                common.REPO_ROOT,
                web_env,
            )
        )

    if worker:
        tasks.append(
            (
                "worker",
                ["ade-worker"],
                common.REPO_ROOT,
                env,
            )
        )

    typer.echo("")
    typer.echo("🚀 Starting dev processes (Ctrl+C to stop)…")
    common.run_parallel(tasks)


def register(app: typer.Typer) -> None:
    @app.command(
        help="Run dev services: API http://localhost:8000, Web http://localhost:5173, Worker (runs migrations first).",
    )
    def dev(
        api: bool = typer.Option(
            True,
            "--api/--no-api",
            help="Run the API dev server.",
        ),
        web: bool = typer.Option(
            True,
            "--web/--no-web",
            help="Run the web dev server.",
        ),
        worker: bool = typer.Option(
            True,
            "--worker/--no-worker",
            help="Run the background worker.",
        ),
        api_only: bool = typer.Option(
            False,
            "--api-only",
            help="Shortcut for API only (same as --api --no-web --no-worker).",
        ),
        web_only: bool = typer.Option(
            False,
            "--web-only",
            help="Shortcut for web only (same as --web --no-api --no-worker).",
        ),
        api_port: int = typer.Option(
            None,
            "--api-port",
            help="Port for the API dev server.",
            envvar="ADE_API_PORT",
        ),
        api_host: str = typer.Option(
            None,
            "--api-host",
            help="Host/interface for the API dev server.",
            envvar="ADE_API_HOST",
        ),
        web_port: int = typer.Option(
            None,
            "--web-port",
            help="Port for the web dev server.",
            envvar="ADE_WEB_PORT",
        ),
        web_host: str = typer.Option(
            None,
            "--web-host",
            help="Host/interface for the web dev server.",
            envvar="ADE_WEB_HOST",
        ),
    ) -> None:
        run_dev(
            api=api,
            web=web,
            worker=worker,
            api_only=api_only,
            web_only=web_only,
            api_port=api_port,
            api_host=api_host,
            web_port=web_port,
            web_host=web_host,
        )
