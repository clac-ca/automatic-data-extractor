"""Root ADE CLI."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE CLI (start, stop, restart, dev, test, reset, api, worker, db, storage, web).",
)

SERVICE_ORDER = ("api", "worker", "web")
SERVICE_SET = set(SERVICE_ORDER)

DEFAULT_INTERNAL_API_URL = "http://localhost:8001"
DEFAULT_API_PROCESSES = 1
DEFAULT_WORKER_RUN_CONCURRENCY = 2
DEFAULT_CHILD_SHUTDOWN_TIMEOUT_SECONDS = 10.0
DEFAULT_STOP_TIMEOUT_SECONDS = 15.0


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

API_PROCESS_PATTERNS = ("ade_api.main:app",)
WORKER_PROCESS_PATTERNS = ("ade-worker start", "ade_worker.worker")
WEB_PROCESS_PATTERNS = (
    "nginx -g daemon off;",
    f"npm --prefix {FRONTEND_DIR} run dev",
    f"{FRONTEND_DIR}/node_modules/vite/bin/vite.js",
    f"{FRONTEND_DIR}/node_modules/.bin/vite",
)


def _run(
    command: Iterable[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd_list = list(command)
    typer.echo(f"-> {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(cmd_list, cwd=cwd, env=env, check=False)
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


def _ps_fallback_pattern(pattern: str) -> set[int]:
    cmd = ["ps", "-eo", "pid=,args="]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return set()
    matches: set[int] = set()
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid_token, args = parts
        try:
            pid = int(pid_token)
        except ValueError:
            continue
        if pattern in args:
            matches.add(pid)
    return matches


def _pgrep_pattern(pattern: str) -> set[int]:
    cmd = ["pgrep", "-f", pattern]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return _ps_fallback_pattern(pattern)
    if completed.returncode not in {0, 1}:
        return set()
    if completed.returncode == 1:
        return set()
    pids: set[int] = set()
    for token in completed.stdout.split():
        try:
            pids.add(int(token))
        except ValueError:
            continue
    return pids


def _find_matching_pids(patterns: Iterable[str]) -> set[int]:
    pids: set[int] = set()
    current_pid = os.getpid()
    for pattern in patterns:
        pids.update(_pgrep_pattern(pattern))
    pids.discard(current_pid)
    return pids


def _list_ade_service_pids() -> dict[str, set[int]]:
    return {
        "api": _find_matching_pids(API_PROCESS_PATTERNS),
        "worker": _find_matching_pids(WORKER_PROCESS_PATTERNS),
        "web": _find_matching_pids(WEB_PROCESS_PATTERNS),
    }


def _all_ade_service_pids(service_pids: dict[str, set[int]]) -> set[int]:
    all_pids: set[int] = set()
    for pids in service_pids.values():
        all_pids.update(pids)
    return all_pids


def _format_service_pids(service_pids: dict[str, set[int]]) -> str:
    parts: list[str] = []
    for service in SERVICE_ORDER:
        pids = sorted(service_pids.get(service, set()))
        if not pids:
            continue
        parts.append(f"{service}={','.join(str(pid) for pid in pids)}")
    return "; ".join(parts)


def _assert_no_running_ade_services() -> None:
    service_pids = _list_ade_service_pids()
    all_pids = _all_ade_service_pids(service_pids)
    if not all_pids:
        return
    summary = _format_service_pids(service_pids)
    typer.echo(
        (
            "error: ADE service processes already running "
            f"({summary}). Use `ade stop` or `ade restart`."
        ),
        err=True,
    )
    raise typer.Exit(code=1)


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_pids_exit(pids: set[int], timeout: float) -> set[int]:
    remaining = {pid for pid in pids if _is_pid_alive(pid)}
    deadline = time.monotonic() + max(timeout, 0.0)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.1)
        remaining = {pid for pid in remaining if _is_pid_alive(pid)}
    return remaining


def _signal_pids(pids: set[int], signum: int) -> None:
    failures: list[int] = []
    for pid in sorted(pids):
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            continue
        except PermissionError:
            failures.append(pid)
    if not failures:
        return
    signal_name = signal.Signals(signum).name
    failure_list = ", ".join(str(pid) for pid in failures)
    typer.echo(
        f"error: permission denied while sending {signal_name} to pid(s): {failure_list}",
        err=True,
    )
    raise typer.Exit(code=1)


def _shutdown_processes(
    processes: dict[str, subprocess.Popen[str]],
    *,
    timeout: float = DEFAULT_CHILD_SHUTDOWN_TIMEOUT_SECONDS,
) -> None:
    for proc in processes.values():
        if proc.poll() is None:
            proc.terminate()

    deadline = time.monotonic() + max(timeout, 0.0)
    while time.monotonic() < deadline:
        if all(proc.poll() is not None for proc in processes.values()):
            return
        time.sleep(0.1)

    for name, proc in processes.items():
        if proc.poll() is None:
            typer.echo(f"warning: force-killing {name} (pid {proc.pid})", err=True)
            proc.kill()

    for proc in processes.values():
        if proc.poll() is None:
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue


def _spawn_processes(
    commands: dict[str, tuple[list[str], dict[str, str] | None]],
    *,
    cwd: Path,
) -> None:
    processes: dict[str, subprocess.Popen[str]] = {}
    shutdown_signal: int | None = None
    original_handlers: list[tuple[int, signal.Handlers]] = []

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutdown_signal
        shutdown_signal = signum

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            original_handlers.append((signum, signal.getsignal(signum)))
            signal.signal(signum, _handle_signal)

        for name, (cmd, env) in commands.items():
            typer.echo(f"-> {' '.join(cmd)}", err=True)
            processes[name] = subprocess.Popen(cmd, cwd=cwd, env=env)

        while True:
            if shutdown_signal is not None:
                _shutdown_processes(processes)
                raise typer.Exit(code=128 + shutdown_signal)
            for name, proc in processes.items():
                ret = proc.poll()
                if ret is not None:
                    typer.echo(f"warning: {name} exited with code {ret}", err=True)
                    _shutdown_processes(processes)
                    raise typer.Exit(code=ret)
            time.sleep(0.2)
    except KeyboardInterrupt:
        _shutdown_processes(processes)
        raise typer.Exit(code=130) from None
    finally:
        for signum, previous in original_handlers:
            signal.signal(signum, previous)


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


def _env_value(env: dict[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _resolve_internal_api_url(env: dict[str, str]) -> str:
    raw = _env_value(env, "ADE_INTERNAL_API_URL") or DEFAULT_INTERNAL_API_URL
    trimmed = raw.rstrip("/")
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        typer.echo(
            "error: ADE_INTERNAL_API_URL must be an origin like http://localhost:8001.",
            err=True,
        )
        raise typer.Exit(code=1)
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        typer.echo(
            "error: ADE_INTERNAL_API_URL must not include a path/query/fragment (no /api).",
            err=True,
        )
        raise typer.Exit(code=1)
    return f"{parsed.scheme}://{parsed.netloc}"


def _nginx_cmd() -> list[str]:
    nginx_bin = shutil.which("nginx")
    if not nginx_bin:
        typer.echo("error: nginx not found in PATH.", err=True)
        raise typer.Exit(code=1)
    return [nginx_bin, "-g", "daemon off;"]


def _maybe_run_migrations(selected: list[str], migrate: bool) -> None:
    if not any(service in {"api", "worker"} for service in selected):
        typer.echo("-> skip migrations (no api/worker selected)", err=True)
        return
    if not migrate:
        typer.echo("-> skip migrations (--no-migrate)", err=True)
        return
    typer.echo("-> running database migrations", err=True)
    _run(["ade", "db", "migrate"], cwd=REPO_ROOT)


def _npm_cmd(*args: str) -> list[str]:
    return ["npm", "--prefix", str(FRONTEND_DIR), *args]


def _print_effective_runtime_config(
    *,
    mode: str,
    selected: list[str],
    migrate: bool,
    env: dict[str, str],
    internal_api_url: str | None,
) -> None:
    api_processes = _env_value(env, "ADE_API_PROCESSES") or str(DEFAULT_API_PROCESSES)
    worker_run_concurrency = _env_value(env, "ADE_WORKER_RUN_CONCURRENCY") or str(
        DEFAULT_WORKER_RUN_CONCURRENCY
    )
    auth_disabled = _env_value(env, "ADE_AUTH_DISABLED") or "false"
    public_web_url = _env_value(env, "ADE_PUBLIC_WEB_URL") or "http://localhost:8000"

    typer.echo("ADE runtime configuration:", err=True)
    typer.echo(f"  mode: {mode}", err=True)
    typer.echo(f"  services: {','.join(selected)}", err=True)
    typer.echo(f"  migrate_on_start: {str(migrate).lower()}", err=True)
    if "api" in selected:
        if mode == "dev":
            typer.echo(
                "  api.processes: 1 (dev reload mode; use `ade api dev --processes N` to override)",
                err=True,
            )
        else:
            typer.echo(f"  api.processes: {api_processes}", err=True)
    if "worker" in selected:
        typer.echo(f"  worker.run_concurrency: {worker_run_concurrency}", err=True)
    if "web" in selected and internal_api_url is not None:
        typer.echo(f"  web.internal_api_url: {internal_api_url}", err=True)
    typer.echo(f"  auth.disabled: {auth_disabled}", err=True)
    typer.echo(f"  public_web_url: {public_web_url}", err=True)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _build_root_commands(
    *,
    mode: str,
    selected: list[str],
    base_env: dict[str, str],
    internal_api_url: str | None,
) -> dict[str, tuple[list[str], dict[str, str] | None]]:
    commands: dict[str, tuple[list[str], dict[str, str] | None]] = {}
    if "api" in selected:
        api_mode = "start" if mode == "start" else "dev"
        commands["api"] = (["ade-api", api_mode], base_env)
    if "worker" in selected:
        commands["worker"] = (["ade-worker", "start"], base_env)
    if "web" in selected:
        web_env = base_env.copy()
        web_env["ADE_INTERNAL_API_URL"] = internal_api_url or DEFAULT_INTERNAL_API_URL
        web_cmd = _nginx_cmd() if mode == "start" else _npm_cmd("run", "dev")
        commands["web"] = (web_cmd, web_env)
    return commands


def _run_root_mode(*, mode: str, services: str | None, migrate: bool) -> None:
    selected = _parse_services(services)
    _assert_no_running_ade_services()
    base_env = os.environ.copy()
    internal_api_url: str | None = None
    if "web" in selected:
        internal_api_url = _resolve_internal_api_url(base_env)
    if (
        mode == "dev"
        and "api" in selected
        and _env_value(base_env, "ADE_API_PROCESSES") is not None
    ):
        typer.echo(
            "warning: ADE_API_PROCESSES is ignored by `ade dev`; use `ade api dev --processes N`.",
            err=True,
        )
    _print_effective_runtime_config(
        mode=mode,
        selected=selected,
        migrate=migrate,
        env=base_env,
        internal_api_url=internal_api_url,
    )
    _maybe_run_migrations(selected, migrate)
    commands = _build_root_commands(
        mode=mode,
        selected=selected,
        base_env=base_env,
        internal_api_url=internal_api_url,
    )
    _spawn_processes(commands, cwd=REPO_ROOT)


def _stop_ade_services(*, timeout: float) -> None:
    service_pids = _list_ade_service_pids()
    all_pids = _all_ade_service_pids(service_pids)
    if not all_pids:
        typer.echo("-> nothing to stop (no matching ADE service processes).", err=True)
        return

    summary = _format_service_pids(service_pids)
    typer.echo(f"-> stopping ADE services ({summary})", err=True)
    _signal_pids(all_pids, signal.SIGTERM)
    remaining = _wait_for_pids_exit(all_pids, timeout)
    if not remaining:
        typer.echo("-> ADE services stopped.", err=True)
        return

    remaining_list = ", ".join(str(pid) for pid in sorted(remaining))
    typer.echo(
        (
            f"warning: {len(remaining)} process(es) did not exit within {timeout:.1f}s; "
            f"sending SIGKILL to pid(s): {remaining_list}"
        ),
        err=True,
    )
    _signal_pids(remaining, signal.SIGKILL)
    survivors = _wait_for_pids_exit(remaining, 2.0)
    if survivors:
        survivor_list = ", ".join(str(pid) for pid in sorted(survivors))
        typer.echo(f"error: ADE process(es) still running: {survivor_list}", err=True)
        raise typer.Exit(code=1)
    typer.echo("-> ADE services force-stopped.", err=True)


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
    _run_root_mode(mode="start", services=services, migrate=migrate)


@app.command(name="stop", help="Stop running ADE service processes.")
def stop(
    timeout: float = typer.Option(
        DEFAULT_STOP_TIMEOUT_SECONDS,
        "--timeout",
        help="Seconds to wait after SIGTERM before force-stopping with SIGKILL.",
        min=0.0,
    ),
) -> None:
    _stop_ade_services(timeout=timeout)


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
    _run_root_mode(mode="dev", services=services, migrate=migrate)


@app.command(name="restart", help="Stop ADE services, then start them again.")
def restart(
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to run after restart (api,worker,web).",
        envvar="ADE_SERVICES",
    ),
    migrate: bool = typer.Option(
        True,
        "--migrate/--no-migrate",
        help="Run database migrations before starting services.",
        envvar="ADE_DB_MIGRATE_ON_START",
    ),
    timeout: float = typer.Option(
        DEFAULT_STOP_TIMEOUT_SECONDS,
        "--timeout",
        help="Seconds to wait during stop before force-stopping with SIGKILL.",
        min=0.0,
    ),
) -> None:
    _stop_ade_services(timeout=timeout)
    _run_root_mode(mode="start", services=services, migrate=migrate)


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
        _run(["ade-db", "reset", "--yes"], cwd=REPO_ROOT)
    if storage:
        _run(
            ["ade-storage", "reset", "--yes", "--mode", storage_mode.value],
            cwd=REPO_ROOT,
        )
    if data:
        data_dir = REPO_ROOT / "backend" / "data"
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


@web_app.command(name="start", help="Serve built frontend via nginx.")
def web_start() -> None:
    base_env = os.environ.copy()
    web_env = base_env.copy()
    web_env["ADE_INTERNAL_API_URL"] = _resolve_internal_api_url(base_env)
    _run(_nginx_cmd(), cwd=REPO_ROOT, env=web_env)


@web_app.command(name="dev", help="Run Vite dev server.")
def web_dev() -> None:
    base_env = os.environ.copy()
    web_env = base_env.copy()
    web_env["ADE_INTERNAL_API_URL"] = _resolve_internal_api_url(base_env)
    _run(_npm_cmd("run", "dev"), cwd=REPO_ROOT, env=web_env)


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
