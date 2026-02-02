"""Root ADE CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import typer
from alembic import command

from ade_db.migrations_runner import alembic_config, run_migrations

app = typer.Typer(add_completion=False, help="ADE CLI (api, worker, web, db).")

SERVICE_ORDER = ("api", "worker", "web")
SERVICE_SET = set(SERVICE_ORDER)


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


def _spawn_processes(commands: dict[str, list[str]], *, cwd: Path) -> None:
    processes: dict[str, subprocess.Popen[str]] = {}
    try:
        for name, cmd in commands.items():
            typer.echo(f"-> {' '.join(cmd)}", err=True)
            processes[name] = subprocess.Popen(cmd, cwd=cwd)

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


def _npm_cmd(*args: str) -> list[str]:
    return ["npm", "--prefix", str(FRONTEND_DIR), *args]


@app.command(name="start", help="Start API + worker + web (default).")
def start(
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to run (api,worker,web).",
        envvar="ADE_SERVICES",
    ),
) -> None:
    selected = _parse_services(services)
    commands: dict[str, list[str]] = {}
    if "api" in selected:
        commands["api"] = ["ade-api", "start"]
    if "worker" in selected:
        commands["worker"] = ["ade-worker", "start"]
    if "web" in selected:
        commands["web"] = _web_entrypoint_cmd()
    _spawn_processes(commands, cwd=REPO_ROOT)


@app.command(name="dev", help="Start API + worker + web in dev mode.")
def dev(
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to run (api,worker,web).",
        envvar="ADE_SERVICES",
    ),
) -> None:
    selected = _parse_services(services)
    commands: dict[str, list[str]] = {}
    if "api" in selected:
        commands["api"] = ["ade-api", "dev"]
    if "worker" in selected:
        commands["worker"] = ["ade-worker", "start"]
    if "web" in selected:
        commands["web"] = _npm_cmd("run", "dev")
    _spawn_processes(commands, cwd=REPO_ROOT)


@app.command(name="test", help="Run API, worker, and web tests.")
def test() -> None:
    _run(["ade-api", "test"], cwd=REPO_ROOT)
    _run(["ade-worker", "test"], cwd=REPO_ROOT)
    _run(_npm_cmd("run", "test"), cwd=REPO_ROOT)


# --- Service delegation ----------------------------------------------------

api_app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help="API CLI (delegates to ade-api).",
)


@api_app.callback()
def api(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if not args:
        args = ["--help"]
    _run(["ade-api", *args], cwd=REPO_ROOT)


worker_app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help="Worker CLI (delegates to ade-worker).",
)


@worker_app.callback()
def worker(ctx: typer.Context) -> None:
    args = list(ctx.args)
    if not args:
        args = ["--help"]
    _run(["ade-worker", *args], cwd=REPO_ROOT)


web_app = typer.Typer(add_completion=False, help="Web CLI (frontend).")


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


# --- DB commands -----------------------------------------------------------


db_app = typer.Typer(add_completion=False, help="Database migrations.")


@db_app.command(name="migrate", help="Apply Alembic migrations (upgrade head).")
def db_migrate(
    revision: str = typer.Argument("head", help="Alembic revision to upgrade to."),
) -> None:
    run_migrations(revision=revision)


@db_app.command(name="history", help="Show migration history.")
def db_history(
    rev_range: str | None = typer.Argument(None, help="Revision range (optional)."),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
) -> None:
    with alembic_config() as cfg:
        command.history(cfg, rev_range, verbose=verbose)


@db_app.command(name="current", help="Show current database revision.")
def db_current(
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
) -> None:
    with alembic_config() as cfg:
        command.current(cfg, verbose=verbose)


@db_app.command(name="stamp", help="Stamp revision without running migrations.")
def db_stamp(
    revision: str = typer.Argument(..., help="Alembic revision to stamp."),
) -> None:
    with alembic_config() as cfg:
        command.stamp(cfg, revision)


app.add_typer(api_app, name="api")
app.add_typer(worker_app, name="worker")
app.add_typer(web_app, name="web")
app.add_typer(db_app, name="db")


if __name__ == "__main__":
    app()
