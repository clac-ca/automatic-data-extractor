"""Root ADE CLI."""

from __future__ import annotations

from enum import Enum
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import typer

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE CLI (start, dev, test, reset, api, worker, db, storage, web).",
)

SERVICE_ORDER = ("api", "worker", "web")
SERVICE_SET = set(SERVICE_ORDER)


class StorageResetMode(str, Enum):
    PREFIX = "prefix"
    CONTAINER = "container"


def _find_repo_root() -> Path:
    def _is_repo_root(path: Path) -> bool:
        return (path / "backend" / "pyproject.toml").is_file()

    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if _is_repo_root(candidate):
            return candidate

    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if _is_repo_root(candidate):
            return candidate

    return cwd


REPO_ROOT = _find_repo_root()
FRONTEND_DIR = REPO_ROOT / "frontend" / "ade-web"


def _run(command: Iterable[str], *, cwd: Path | None = None) -> None:
    cmd_list = list(command)
    typer.echo(f"-> {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(cmd_list, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


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


def _spawn_processes(
    commands: dict[str, tuple[list[str], dict[str, str] | None]],
    *,
    cwd: Path,
) -> None:
    processes: dict[str, subprocess.Popen[str]] = {}
    try:
        for name, (cmd, env) in commands.items():
            typer.echo(f"-> {' '.join(cmd)}", err=True)
            processes[name] = subprocess.Popen(cmd, cwd=cwd, env=env)

        while True:
            for name, proc in processes.items():
                ret = proc.poll()
                if ret is not None:
                    typer.echo(f"warning: {name} exited with code {ret}", err=True)
                    for other_name, other_proc in processes.items():
                        if other_proc is proc:
                            continue
                        if other_proc.poll() is None:
                            other_proc.terminate()
                    for other_proc in processes.values():
                        if other_proc.poll() is None:
                            other_proc.wait(timeout=10)
                    raise typer.Exit(code=ret)
            time.sleep(0.2)
    except KeyboardInterrupt:
        for proc in processes.values():
            if proc.poll() is None:
                proc.terminate()
        for proc in processes.values():
            if proc.poll() is None:
                proc.wait(timeout=10)
        raise typer.Exit(code=130) from None


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
    ordered = [svc for svc in SERVICE_ORDER if svc in tokens]
    return ordered


def _web_entrypoint_cmd() -> list[str]:
    entrypoint = shutil.which("ade-web-entrypoint")
    if entrypoint:
        return [entrypoint]
    script = FRONTEND_DIR / "nginx" / "entrypoint.sh"
    if not script.exists():
        typer.echo(
            "error: web entrypoint not found (expected frontend/ade-web/nginx/entrypoint.sh).",
            err=True,
        )
        raise typer.Exit(code=1)
    return [str(script)]


def _maybe_run_migrations(selected: list[str], migrate: bool) -> None:
    if not migrate:
        return
    if not any(service in {"api", "worker"} for service in selected):
        return
    _run(["ade", "db", "migrate"], cwd=REPO_ROOT)


def _npm_cmd(*args: str) -> list[str]:
    return ["npm", "--prefix", str(FRONTEND_DIR), *args]


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="start", help="Start API + worker + web (default).")
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
) -> None:
    selected = _parse_services(services)
    _maybe_run_migrations(selected, migrate)
    base_env = os.environ.copy()
    commands: dict[str, tuple[list[str], dict[str, str] | None]] = {}
    api_needs_alt_port = "api" in selected and "web" in selected
    if "api" in selected:
        api_env = base_env.copy()
        if api_needs_alt_port:
            api_env.setdefault("ADE_API_PORT", "8001")
        commands["api"] = (["ade-api", "start"], api_env)
    if "worker" in selected:
        commands["worker"] = (["ade-worker", "start"], base_env)
    if "web" in selected:
        web_env = base_env.copy()
        if api_needs_alt_port:
            web_env.setdefault("ADE_WEB_PROXY_TARGET", "http://127.0.0.1:8001")
        commands["web"] = (_web_entrypoint_cmd(), web_env)
    _spawn_processes(commands, cwd=REPO_ROOT)


@app.command(name="dev", help="Start API + worker + web in dev mode.")
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
) -> None:
    selected = _parse_services(services)
    _maybe_run_migrations(selected, migrate)
    base_env = os.environ.copy()
    commands: dict[str, tuple[list[str], dict[str, str] | None]] = {}
    api_needs_alt_port = "api" in selected and "web" in selected
    if "api" in selected:
        api_env = base_env.copy()
        if api_needs_alt_port:
            api_env.setdefault("ADE_API_PORT", "8001")
        commands["api"] = (["ade-api", "dev"], api_env)
    if "worker" in selected:
        commands["worker"] = (["ade-worker", "start"], base_env)
    if "web" in selected:
        web_env = base_env.copy()
        web_env.setdefault("ADE_WEB_DEV_PORT", "8000")
        if api_needs_alt_port:
            web_env.setdefault("ADE_API_PROXY_TARGET", "http://localhost:8001")
        commands["web"] = (_npm_cmd("run", "dev"), web_env)
    _spawn_processes(commands, cwd=REPO_ROOT)


@app.command(name="test", help="Run API, worker, and web tests.")
def test() -> None:
    _run(["ade-api", "test"], cwd=REPO_ROOT)
    _run(["ade-worker", "test"], cwd=REPO_ROOT)
    _run(_npm_cmd("run", "test"), cwd=REPO_ROOT)


@app.command(name="reset", help="Reset DB, storage, and local state (destructive).")
def reset(
    db: bool = typer.Option(True, "--db/--no-db", help="Reset the database."),
    storage: bool = typer.Option(True, "--storage/--no-storage", help="Reset blob storage."),
    data: bool = typer.Option(True, "--data/--no-data", help="Clear local data directory."),
    venv: bool = typer.Option(True, "--venv/--no-venv", help="Remove local virtualenvs."),
    storage_mode: StorageResetMode = typer.Option(
        StorageResetMode.PREFIX,
        "--storage-mode",
        help="Storage reset mode: prefix (default) or container.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Confirm destructive reset."),
) -> None:
    if not yes:
        typer.echo("error: reset requires --yes", err=True)
        raise typer.Exit(code=1)

    if db:
        _run(["ade-db", "reset", "--yes"], cwd=REPO_ROOT)
    if storage:
        _run(
            ["ade-storage", "reset", "--yes", "--mode", storage_mode.value],
            cwd=REPO_ROOT,
        )
    if data:
        data_dir = REPO_ROOT / "data"
        if data_dir.exists():
            shutil.rmtree(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    if venv:
        _remove_dir(REPO_ROOT / ".venv")
        _remove_dir(REPO_ROOT / "backend" / ".venv")


# --- Service delegation ----------------------------------------------------


@app.command(
    name="api",
    help="API CLI (delegates to ade-api).",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
def api(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if args and args[0] == ctx.info_name:
        args = args[1:]
    if not args:
        args = ["--help"]
    _run(["ade-api", *args], cwd=REPO_ROOT)


@app.command(
    name="worker",
    help="Worker CLI (delegates to ade-worker).",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
def worker(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if args and args[0] == ctx.info_name:
        args = args[1:]
    if not args:
        args = ["--help"]
    _run(["ade-worker", *args], cwd=REPO_ROOT)


@app.command(
    name="db",
    help="Database CLI (delegates to ade-db).",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
def db(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if args and args[0] == ctx.info_name:
        args = args[1:]
    if not args:
        args = ["--help"]
    _run(["ade-db", *args], cwd=REPO_ROOT)


@app.command(
    name="storage",
    help="Storage CLI (delegates to ade-storage).",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
)
def storage(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if args and args[0] == ctx.info_name:
        args = args[1:]
    if not args:
        args = ["--help"]
    _run(["ade-storage", *args], cwd=REPO_ROOT)


web_app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Web CLI (frontend).",
)


@web_app.callback()
def web(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@web_app.command(name="start", help="Serve built frontend via nginx entrypoint.")
def web_start() -> None:
    _run(_web_entrypoint_cmd(), cwd=REPO_ROOT)


@web_app.command(name="dev", help="Run Vite dev server.")
def web_dev() -> None:
    _run(_npm_cmd("run", "dev"), cwd=REPO_ROOT)


@web_app.command(name="build", help="Build frontend assets.")
def web_build() -> None:
    _run(_npm_cmd("run", "build"), cwd=REPO_ROOT)


@web_app.command(name="test", help="Run frontend tests.")
def web_test() -> None:
    _run(_npm_cmd("run", "test"), cwd=REPO_ROOT)


@web_app.command(name="test:watch", help="Run frontend tests in watch mode.")
def web_test_watch() -> None:
    _run(_npm_cmd("run", "test:watch"), cwd=REPO_ROOT)


@web_app.command(name="test:coverage", help="Run frontend tests with coverage.")
def web_test_coverage() -> None:
    _run(_npm_cmd("run", "test:coverage"), cwd=REPO_ROOT)


@web_app.command(name="lint", help="Lint frontend code.")
def web_lint() -> None:
    _run(_npm_cmd("run", "lint"), cwd=REPO_ROOT)


@web_app.command(name="typecheck", help="Typecheck frontend code.")
def web_typecheck() -> None:
    _run(_npm_cmd("run", "typecheck"), cwd=REPO_ROOT)


@web_app.command(name="preview", help="Preview built frontend.")
def web_preview() -> None:
    _run(_npm_cmd("run", "preview"), cwd=REPO_ROOT)


app.add_typer(web_app, name="web")


if __name__ == "__main__":
    app()
