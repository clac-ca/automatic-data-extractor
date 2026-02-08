"""ADE root/orchestrator CLI."""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

from paths import BACKEND_ROOT, REPO_ROOT

from .api import app as api_app
from .common import ManagedProcess, run, run_many
from .db import app as db_app
from .infra import app as infra_app
from .local_dev import missing_core_runtime_env
from .storage import app as storage_app
from .web import app as web_app, resolve_public_web_url
from .worker import app as worker_app

SERVICE_ORDER = ("api", "worker", "web")
SERVICE_SET = set(SERVICE_ORDER)


class StorageResetMode(str, Enum):
    PREFIX = "prefix"
    CONTAINER = "container"


app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE root CLI (mounts ADE CLI subcommands).",
)


def _parse_services(value: str | None) -> list[str]:
    raw = value or os.getenv("ADE_SERVICES") or "api,worker,web"
    tokens = [token.strip().lower() for token in raw.split(",") if token.strip()]
    if not tokens:
        return list(SERVICE_ORDER)
    if "all" in tokens or "*" in tokens:
        return list(SERVICE_ORDER)
    unknown = sorted(set(tokens) - SERVICE_SET)
    if unknown:
        typer.echo(f"error: unknown service(s): {', '.join(unknown)}", err=True)
        raise typer.Exit(code=1)
    return [service for service in SERVICE_ORDER if service in tokens]


def _build_processes(*, mode: str, selected: list[str]) -> list[ManagedProcess]:
    processes: list[ManagedProcess] = []
    if "api" in selected:
        api_mode = "start" if mode == "start" else "dev"
        processes.append(
            ManagedProcess(
                name="api",
                command=[sys.executable, "-m", "ade_api", api_mode],
                env=os.environ.copy(),
            )
        )
    if "worker" in selected:
        processes.append(
            ManagedProcess(
                name="worker",
                command=[sys.executable, "-m", "ade_worker", "start"],
                env=os.environ.copy(),
            )
        )
    if "web" in selected:
        web_mode = "start" if mode == "start" else "dev"
        processes.append(
            ManagedProcess(
                name="web",
                command=[sys.executable, "-m", "ade_cli", "web", web_mode],
                env=os.environ.copy(),
            )
        )
    return processes


def _maybe_run_migrations(selected: list[str], migrate: bool) -> None:
    if not any(service in {"api", "worker"} for service in selected):
        return
    if not migrate:
        typer.echo("-> skipping migrations (--no-migrate)", err=True)
        return
    typer.echo("-> running database migrations", err=True)
    run([sys.executable, "-m", "ade_db", "migrate"], cwd=REPO_ROOT)


def _is_port_open(host: str, port: int, *, timeout_seconds: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _open_browser_when_ready(
    url: str,
    *,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.4,
) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    def _worker() -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if _is_port_open(host, port):
                status = typer.launch(url)
                if status != 0:
                    typer.echo(
                        f"warning: failed to open browser automatically (exit code {status}).",
                        err=True,
                    )
                    typer.echo(f"Open manually: {url}", err=True)
                return
            time.sleep(poll_interval_seconds)

        typer.echo(
            f"warning: timed out waiting for web service at {host}:{port}; "
            "browser was not opened automatically.",
            err=True,
        )
        typer.echo(f"Open manually: {url}", err=True)

    threading.Thread(target=_worker, name="ade-open-browser", daemon=True).start()


def _maybe_open_browser(*, selected: list[str], open_in_browser: bool) -> None:
    if not open_in_browser:
        return
    if "web" not in selected:
        typer.echo("warning: --open ignored because web service is not selected.", err=True)
        return
    try:
        url = resolve_public_web_url(os.environ)
    except typer.Exit:
        typer.echo(
            "warning: unable to resolve web URL for --open; services will continue running.",
            err=True,
        )
        return
    except Exception as exc:  # pragma: no cover - defensive guardrail
        typer.echo(
            f"warning: unable to resolve web URL for --open ({exc}); "
            "services will continue running.",
            err=True,
        )
        return

    typer.echo(f"-> will open browser when web is ready: {url}", err=True)
    _open_browser_when_ready(url)


def _exit_with_local_infra_hint(reason: str) -> None:
    typer.echo(f"error: {reason}", err=True)
    typer.echo("hint: run `cd backend && uv run ade infra up`.", err=True)
    raise typer.Exit(code=1)


def _preflight_runtime(selected: list[str]) -> None:
    if not any(service in {"api", "worker"} for service in selected):
        return

    missing = missing_core_runtime_env()
    if missing:
        _exit_with_local_infra_hint(
            f"missing required runtime settings: {', '.join(missing)}"
        )

    if not os.getenv("ADE_LOCAL_PROFILE_ID"):
        return

    database_url = os.getenv("ADE_DATABASE_URL", "")
    parsed = urlparse(database_url)
    db_host = parsed.hostname
    db_port = parsed.port
    if db_host and db_port and db_host in {"127.0.0.1", "localhost"}:
        if not _is_port_open(db_host, db_port):
            _exit_with_local_infra_hint(
                f"local Postgres is not reachable at {db_host}:{db_port}"
            )

    blob_port_raw = os.getenv("ADE_LOCAL_BLOB_PORT")
    if blob_port_raw and blob_port_raw.isdigit():
        blob_port = int(blob_port_raw)
        if not _is_port_open("127.0.0.1", blob_port):
            _exit_with_local_infra_hint(
                f"local Azurite blob service is not reachable at 127.0.0.1:{blob_port}"
            )


def _clean_test_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in tuple(env.keys()):
        if key.startswith("ADE_"):
            env.pop(key, None)
    return env


def _is_current_venv(path: Path) -> bool:
    try:
        return Path(sys.prefix).resolve().is_relative_to(path.resolve())
    except ValueError:
        return False


def _remove_dir(path: Path) -> None:
    if not path.exists():
        return
    if _is_current_venv(path):
        typer.echo(f"warning: skipping removal of active virtualenv at {path}", err=True)
        return
    shutil.rmtree(path)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="start", help="Run selected services in start mode.")
def start(
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to run (api,worker,web).",
        envvar="ADE_SERVICES",
    ),
    migrate: bool = typer.Option(
        True,
        "--migrate/--no-migrate",
        help="Run database migrations before starting services.",
        envvar="ADE_DB_MIGRATE_ON_START",
    ),
    open_in_browser: bool = typer.Option(
        False,
        "--open",
        help="Open ADE web in the default browser once the web service is reachable.",
    ),
) -> None:
    selected = _parse_services(services)
    _preflight_runtime(selected)
    _maybe_run_migrations(selected, migrate)
    _maybe_open_browser(selected=selected, open_in_browser=open_in_browser)
    run_many(_build_processes(mode="start", selected=selected), cwd=REPO_ROOT)


@app.command(name="dev", help="Run selected services in dev mode.")
def dev(
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to run (api,worker,web).",
        envvar="ADE_SERVICES",
    ),
    migrate: bool = typer.Option(
        True,
        "--migrate/--no-migrate",
        help="Run database migrations before starting services.",
        envvar="ADE_DB_MIGRATE_ON_START",
    ),
    open_in_browser: bool = typer.Option(
        False,
        "--open",
        help="Open ADE web in the default browser once the web service is reachable.",
    ),
) -> None:
    selected = _parse_services(services)
    _preflight_runtime(selected)
    _maybe_run_migrations(selected, migrate)
    _maybe_open_browser(selected=selected, open_in_browser=open_in_browser)
    run_many(_build_processes(mode="dev", selected=selected), cwd=REPO_ROOT)


@app.command(name="test", help="Run API, worker, and web tests.")
def test() -> None:
    env = _clean_test_env()
    run([sys.executable, "-m", "ade_api", "test"], cwd=REPO_ROOT, env=env)
    run([sys.executable, "-m", "ade_worker", "test"], cwd=REPO_ROOT, env=env)
    run([sys.executable, "-m", "ade_cli", "web", "test"], cwd=REPO_ROOT, env=env)


@app.command(name="reset", help="Reset DB, storage, and local state (destructive).")
def reset(
    db: bool = typer.Option(True, "--db/--no-db", help="Reset the database."),
    storage: bool = typer.Option(True, "--storage/--no-storage", help="Reset blob storage."),
    data: bool = typer.Option(True, "--data/--no-data", help="Clear local data directory."),
    venv: bool = typer.Option(True, "--venv/--no-venv", help="Remove local virtualenvs."),
    storage_mode: Annotated[
        StorageResetMode,
        typer.Option(
            "--storage-mode",
            help="Storage reset mode: prefix (default) or container.",
        ),
    ] = StorageResetMode.PREFIX,
    yes: bool = typer.Option(False, "--yes", help="Confirm destructive reset."),
) -> None:
    if not yes:
        typer.echo("error: reset requires --yes", err=True)
        raise typer.Exit(code=1)

    if db:
        run([sys.executable, "-m", "ade_db", "reset", "--yes"], cwd=REPO_ROOT)
    if storage:
        run(
            [
                sys.executable,
                "-m",
                "ade_storage",
                "reset",
                "--yes",
                "--mode",
                storage_mode.value,
            ],
            cwd=REPO_ROOT,
        )
    if data:
        data_dir = BACKEND_ROOT / "data"
        if data_dir.exists():
            shutil.rmtree(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    if venv:
        _remove_dir(BACKEND_ROOT / ".venv")
        _remove_dir(REPO_ROOT / ".venv")


app.add_typer(api_app, name="api")
app.add_typer(worker_app, name="worker")
app.add_typer(db_app, name="db")
app.add_typer(storage_app, name="storage")
app.add_typer(web_app, name="web")
app.add_typer(infra_app, name="infra")

__all__ = ["app"]


if __name__ == "__main__":
    app()
