"""Start command."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_cli.commands import common
from ade_cli.commands.init_cmd import ensure_sql_database, ensure_storage_defaults
from ade_cli.commands.migrate import run_migrate


def _prepare_env(env: dict[str, str] | None = None) -> dict[str, str]:
    env = env or common.build_env()
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = f"{python_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _ensure_frontend_dist(env: dict[str, str], *, web: bool) -> None:
    if not web:
        env.pop("ADE_FRONTEND_DIST_DIR", None)
        return

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


def _build_api_task(
    env: dict[str, str],
    *,
    api_port: int | None,
    api_host: str | None,
    api_workers: int | None,
    web: bool,
) -> tuple[tuple[str, list[str], Path | None, dict[str, str]], str, int]:
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE dependencies (run `bash scripts/dev/setup.sh`).",
    )
    common.uvicorn_path()

    _ensure_frontend_dist(env, web=web)

    from ade_api.settings import Settings

    api_settings = Settings()
    if api_port is None:
        api_port = api_settings.api_port if api_settings.api_port is not None else 8000
    api_port = int(api_port)
    if api_host is None:
        api_host = api_settings.api_host or "0.0.0.0"
    if api_workers is None:
        api_workers = api_settings.api_workers if api_settings.api_workers is not None else 3
    api_workers = int(api_workers)

    uvicorn_bin = common.uvicorn_path()
    api_import = "ade_api.main:app"
    api_cmd = [
        uvicorn_bin,
        api_import,
        "--host",
        api_host,
        "--port",
        str(api_port),
    ]
    if api_workers and api_workers > 1:
        api_cmd.extend(["--workers", str(api_workers)])

    task = ("api", api_cmd, common.REPO_ROOT, env)
    return task, api_host, api_port


def run_api(
    api_port: int | None = None,
    api_host: str | None = None,
    api_workers: int | None = None,
    web: bool = True,
) -> None:
    """Start ADE API (runs migrations, serves web if enabled)."""
    common.refresh_paths()

    env = _prepare_env()
    ensure_storage_defaults(env)

    task, resolved_host, resolved_port = _build_api_task(
        env,
        api_port=api_port,
        api_host=api_host,
        api_workers=api_workers,
        web=web,
    )

    typer.echo("🗄️  Running migrations…")
    run_migrate()

    typer.echo(f"🚀 Starting ADE API on http://{resolved_host}:{resolved_port}")
    common.run_parallel([task])


def run_start(
    api_port: int | None = None,
    api_host: str | None = None,
    api_workers: int | None = None,
    web: bool = True,
) -> None:
    """Start ADE API + worker (single-container mode)."""
    common.refresh_paths()

    env = _prepare_env()
    ensure_storage_defaults(env)
    ensure_sql_database(env)

    common.require_python_module(
        "ade_worker",
        "Install ADE dependencies (run `bash scripts/dev/setup.sh`).",
    )

    task, resolved_host, resolved_port = _build_api_task(
        env,
        api_port=api_port,
        api_host=api_host,
        api_workers=api_workers,
        web=web,
    )

    typer.echo("🗄️  Running migrations…")
    run_migrate()

    worker_task = ("worker", ["ade-worker"], common.REPO_ROOT, env)

    typer.echo(f"🚀 Starting ADE API on http://{resolved_host}:{resolved_port}")
    typer.echo("🧵 Starting ADE worker…")
    common.run_parallel([task, worker_task])


def register(app: typer.Typer) -> None:
    @app.command(
        name="start",
        help="Start ADE API + worker (single-container mode). Runs init + migrations.",
    )
    def start(
        api_port: int = typer.Option(
            None,
            "--api-port",
            help="Port for the API server.",
            envvar="ADE_API_PORT",
        ),
        api_host: str = typer.Option(
            None,
            "--api-host",
            help="Host/interface for the API server.",
            envvar="ADE_API_HOST",
        ),
        api_workers: int = typer.Option(
            None,
            "--api-workers",
            help="Number of API worker processes (uvicorn).",
            envvar="ADE_API_WORKERS",
            min=1,
        ),
        web: bool = typer.Option(
            True,
            "--web/--no-web",
            help="Serve the built frontend from this process.",
        ),
    ) -> None:
        run_start(
            api_port=api_port,
            api_host=api_host,
            api_workers=api_workers,
            web=web,
        )

    @app.command(
        name="api",
        help="Start ADE API only (runs migrations; serves web if enabled).",
    )
    def api(
        api_port: int = typer.Option(
            None,
            "--api-port",
            help="Port for the API server.",
            envvar="ADE_API_PORT",
        ),
        api_host: str = typer.Option(
            None,
            "--api-host",
            help="Host/interface for the API server.",
            envvar="ADE_API_HOST",
        ),
        api_workers: int = typer.Option(
            None,
            "--api-workers",
            help="Number of API worker processes (uvicorn).",
            envvar="ADE_API_WORKERS",
            min=1,
        ),
        web: bool = typer.Option(
            True,
            "--web/--no-web",
            help="Serve the built frontend from this process.",
        ),
    ) -> None:
        run_api(
            api_port=api_port,
            api_host=api_host,
            api_workers=api_workers,
            web=web,
        )
