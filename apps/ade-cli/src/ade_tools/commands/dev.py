"""Dev command."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from ade_tools.commands import common


def run_dev(
    backend: bool = True,
    frontend: bool = True,
    backend_only: bool = False,
    frontend_only: bool = False,
    backend_port: int | None = None,
    frontend_port: int | None = None,
) -> None:
    """
    Run FastAPI and Vite dev servers with sensible defaults.

    By default runs both:
      - Backend (FastAPI + uvicorn --reload) → http://localhost:8001
      - Frontend (Vite dev server)          → http://localhost:8000

    Port behavior:
      - If both backend and frontend run:
          backend → 8001 (or DEV_BACKEND_PORT / --backend-port)
          frontend → 8000 (or DEV_FRONTEND_PORT / --frontend-port)
      - If only backend runs:
          backend → 8000 (or DEV_BACKEND_PORT / --backend-port)
    """
    common.refresh_paths()

    # Resolve selection flags
    if backend_only and frontend_only:
        typer.echo("❌ Cannot use --backend-only and --frontend-only together.", err=True)
        raise typer.Exit(code=1)

    if backend_only:
        backend, frontend = True, False
    elif frontend_only:
        backend, frontend = False, True

    if not backend and not frontend:
        typer.echo("⚠️ Neither backend nor frontend selected; nothing to run.", err=True)
        raise typer.Exit(code=1)

    backend_present = common.BACKEND_SRC.exists()
    frontend_present = common.FRONTEND_DIR.exists()

    # Soften failures: skip missing pieces instead of just dying
    if backend and not backend_present:
        typer.echo("⚠️ Backend source directory not found; skipping backend.", err=True)
        backend = False

    if frontend and not frontend_present:
        typer.echo("⚠️ Frontend directory not found; skipping frontend.", err=True)
        frontend = False

    if not backend and not frontend:
        typer.echo("Nothing to run yet. Add apps/ade-api/ and/or apps/ade-web/ first.")
        raise typer.Exit(code=0)

    env = os.environ.copy()

    # Resolve ports: CLI overrides > env vars > defaults
    raw_backend_port = (
        str(backend_port)
        if backend_port is not None
        else env.get("DEV_BACKEND_PORT")
    )
    raw_frontend_port = (
        str(frontend_port)
        if frontend_port is not None
        else env.get("DEV_FRONTEND_PORT")
    )

    frontend_pkg_path = common.FRONTEND_DIR / "package.json"
    if frontend and not frontend_pkg_path.exists():
        typer.echo("⚠️  frontend package.json not found; skipping frontend.", err=True)
        frontend = False

    if backend:
        if raw_backend_port is None:
            raw_backend_port = "8001" if frontend else "8000"
        env["DEV_BACKEND_PORT"] = raw_backend_port

    if frontend:
        if raw_frontend_port is None:
            raw_frontend_port = "8000"
        env["DEV_FRONTEND_PORT"] = raw_frontend_port

    tasks: list[tuple[str, list[str], Path | None, dict[str, str]]] = []

    if backend:
        common.require_python_module(
            "ade_api",
            "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
        )
        uvicorn_bin = common.uvicorn_path()
        typer.echo(f"🔧 Backend dev server:    http://localhost:{env['DEV_BACKEND_PORT']}")
        backend_cmd = [
            uvicorn_bin,
            "ade_api.main:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            env["DEV_BACKEND_PORT"],
            "--reload",
            # Restrict reload watching to backend code (avoid data/ workspace churn).
            "--reload-dir",
            str(common.BACKEND_DIR),
        ]
        tasks.append(("backend", backend_cmd, common.REPO_ROOT, env))

    if frontend:
        npm_bin = common.npm_path()
        common.ensure_node_modules()
        typer.echo(f"💻 Frontend dev server:  http://localhost:{env['DEV_FRONTEND_PORT']}")
        frontend_cmd = [
            npm_bin,
            "run",
            "dev",
            "--",
            "--host",
            "0.0.0.0",
            "--port",
            env["DEV_FRONTEND_PORT"],
        ]
        tasks.append(("frontend", frontend_cmd, common.FRONTEND_DIR, env))

    if not tasks:
        typer.echo("Nothing to run yet. Add apps/ade-api/ and/or apps/ade-web/ first.")
        raise typer.Exit(code=0)

    typer.echo("")
    typer.echo("🚀 Starting dev processes (Ctrl+C to stop)…")
    common.run_parallel(tasks)


def register(app: typer.Typer) -> None:
    @app.command(
        help="Run dev servers: FastAPI http://localhost:8001 and Vite http://localhost:8000; flags: --backend-only, --frontend-only, --backend-port <p>, --frontend-port <p>.",
    )
    def dev(
        backend: bool = typer.Option(
            True,
            "--backend/--no-backend",
            help="Run the backend dev server.",
        ),
        frontend: bool = typer.Option(
            True,
            "--frontend/--no-frontend",
            help="Run the frontend dev server.",
        ),
        backend_only: bool = typer.Option(
            False,
            "--backend-only",
            help="Shortcut for backend only (same as --backend --no-frontend).",
        ),
        frontend_only: bool = typer.Option(
            False,
            "--frontend-only",
            help="Shortcut for frontend only (same as --frontend --no-backend).",
        ),
        backend_port: int | None = typer.Option(
            None,
            "--backend-port",
            help="Port for the backend dev server (overrides DEV_BACKEND_PORT).",
        ),
        frontend_port: int | None = typer.Option(
            None,
            "--frontend-port",
            help="Port for the frontend dev server (overrides DEV_FRONTEND_PORT).",
        ),
    ) -> None:
        run_dev(
            backend=backend,
            frontend=frontend,
            backend_only=backend_only,
            frontend_only=frontend_only,
            backend_port=backend_port,
            frontend_port=frontend_port,
        )
