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


def _resolve_selection(
    api: bool | None,
    web: bool | None,
    worker: bool | None,
    api_only: bool,
    web_only: bool,
    worker_only: bool,
) -> tuple[bool, bool, bool]:
    if sum(1 for flag in (api_only, web_only, worker_only) if flag) > 1:
        typer.echo("❌ Only one of --api-only/--web-only/--worker-only may be used.", err=True)
        raise typer.Exit(code=1)

    if api_only:
        return True, False, False
    if web_only:
        return False, True, False
    if worker_only:
        return False, False, True

    explicit_true = any(value is True for value in (api, web, worker))
    if explicit_true:
        return api is True, web is True, worker is True

    # Default: enable all unless explicitly disabled.
    return api is not False, web is not False, worker is not False


def run_dev(
    api: bool | None = None,
    web: bool | None = None,
    worker: bool | None = None,
    api_only: bool = False,
    web_only: bool = False,
    worker_only: bool = False,
    api_port: int | None = None,
    api_host: str | None = None,
    api_workers: int | None = None,
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

    api, web, worker = _resolve_selection(api, web, worker, api_only, web_only, worker_only)

    if not api and not web and not worker:
        typer.echo("⚠️ No services selected; nothing to run.", err=True)
        raise typer.Exit(code=1)

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

    api_reload = True
    if api:
        common.require_python_module(
            "ade_api",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-api -e apps/ade-worker`).",
        )
        common.uvicorn_path()
        from ade_api.settings import Settings

        api_settings = Settings()
        if api_port is None:
            api_port = api_settings.api_port if api_settings.api_port is not None else 8000
        api_port = int(api_port)
        if api_host is None:
            api_host = api_settings.api_host or "127.0.0.1"
        if api_workers is None:
            api_workers = api_settings.api_workers if api_settings.api_workers is not None else 1
        api_workers = int(api_workers)

    if api and web and api_port == web_port:
        typer.echo("❌ API and web ports must be different when running both servers.", err=True)
        raise typer.Exit(code=1)

    if api:
        if api_workers > 1:
            api_reload = False
            typer.echo("Note: API workers > 1; disabling reload in dev.")
        typer.echo(f"🔧 API dev server:        http://{api_host}:{api_port}")

    if web:
        common.npm_path()
        common.ensure_node_modules()
        typer.echo(f"💻 Web dev server:        http://{web_host}:{web_port}")

    if worker:
        common.require_python_module(
            "ade_worker",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-worker`).",
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
        api_cmd = [
            uvicorn_bin,
            "ade_api.main:create_app",
            "--factory",
            "--host",
            api_host,
            "--port",
            str(api_port),
        ]
        if api_reload:
            api_cmd.extend(["--reload", "--reload-dir", "apps/ade-api"])
        if api_workers > 1:
            api_cmd.extend(["--workers", str(api_workers)])
        tasks.append(
            (
                "api",
                api_cmd,
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
        help=(
            "Run dev services: API http://localhost:8000, Web http://localhost:5173, Worker. "
            "If any of --api/--web/--worker are explicitly enabled, only those run."
        ),
    )
    def dev(
        api: bool | None = typer.Option(
            None,
            "--api/--no-api",
            help="Run the API dev server.",
        ),
        web: bool | None = typer.Option(
            None,
            "--web/--no-web",
            help="Run the web dev server.",
        ),
        worker: bool | None = typer.Option(
            None,
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
        worker_only: bool = typer.Option(
            False,
            "--worker-only",
            help="Shortcut for worker only (same as --worker --no-api --no-web).",
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
        api_workers: int = typer.Option(
            None,
            "--api-workers",
            help="Number of API worker processes (uvicorn).",
            envvar="ADE_API_WORKERS",
            min=1,
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
            worker_only=worker_only,
            api_port=api_port,
            api_host=api_host,
            api_workers=api_workers,
            web_port=web_port,
            web_host=web_host,
        )
