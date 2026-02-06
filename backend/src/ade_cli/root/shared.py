"""Shared helpers for root ADE CLI commands."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

from ade_common.paths import FRONTEND_DIR, REPO_ROOT

SERVICE_ORDER = ("api", "worker", "web")
SERVICE_SET = set(SERVICE_ORDER)

DEFAULT_INTERNAL_API_URL = "http://localhost:8001"
DEFAULT_API_PROCESSES = 1
DEFAULT_WORKER_RUN_CONCURRENCY = 2
DEFAULT_CHILD_SHUTDOWN_TIMEOUT_SECONDS = 10.0
DEFAULT_STOP_TIMEOUT_SECONDS = 15.0

STATE_DIR = REPO_ROOT / ".ade"
STATE_PATH = STATE_DIR / "state.json"


class StorageResetMode(str, Enum):
    PREFIX = "prefix"
    CONTAINER = "container"


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


def _load_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        raw = STATE_PATH.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _write_state(payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _clear_state() -> None:
    STATE_PATH.unlink(missing_ok=True)


def _extract_live_service_pids(state: dict[str, Any] | None) -> dict[str, int]:
    if not state:
        return {}
    processes = state.get("processes")
    if not isinstance(processes, dict):
        return {}

    live: dict[str, int] = {}
    for service in SERVICE_ORDER:
        raw = processes.get(service)
        if not isinstance(raw, dict):
            continue
        pid = raw.get("pid")
        if not isinstance(pid, int):
            continue
        if _is_pid_alive(pid):
            live[service] = pid
    return live


def _persist_runtime_state(
    *,
    mode: str,
    selected: list[str],
    commands: dict[str, tuple[list[str], dict[str, str] | None]],
    processes: dict[str, subprocess.Popen[str]],
) -> None:
    payload: dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "services": selected,
        "cwd": str(REPO_ROOT),
        "started_at": datetime.now(UTC).isoformat(),
        "processes": {},
    }
    proc_payload: dict[str, Any] = payload["processes"]
    for service in selected:
        cmd, _env = commands[service]
        proc_payload[service] = {
            "pid": processes[service].pid,
            "command": cmd,
        }
    _write_state(payload)


def _format_service_pids(service_pids: dict[str, int]) -> str:
    parts = [
        f"{service}={service_pids[service]}"
        for service in SERVICE_ORDER
        if service in service_pids
    ]
    return "; ".join(parts)


def _assert_no_running_ade_services() -> None:
    state = _load_state()
    live = _extract_live_service_pids(state)
    if not live:
        _clear_state()
        return

    summary = _format_service_pids(live)
    typer.echo(
        (
            "error: ADE service processes already running "
            f"({summary}). Use `ade stop` or `ade restart`."
        ),
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
    mode: str,
    selected: list[str],
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

        for name in selected:
            cmd, env = commands[name]
            typer.echo(f"-> {' '.join(cmd)}", err=True)
            processes[name] = subprocess.Popen(cmd, cwd=cwd, env=env)

        _persist_runtime_state(mode=mode, selected=selected, commands=commands, processes=processes)

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
        _clear_state()
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
            (
                "warning: ADE_API_PROCESSES is ignored by `ade dev`; "
                "use `ade api dev --processes N`."
            ),
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
    _spawn_processes(commands, cwd=REPO_ROOT, mode=mode, selected=selected)


def _stop_ade_services(*, timeout: float) -> None:
    state = _load_state()
    live = _extract_live_service_pids(state)
    if not live:
        _clear_state()
        typer.echo("-> nothing to stop (no tracked ADE service processes).", err=True)
        return

    all_pids = set(live.values())
    summary = _format_service_pids(live)
    typer.echo(f"-> stopping ADE services ({summary})", err=True)
    _signal_pids(all_pids, signal.SIGTERM)
    remaining = _wait_for_pids_exit(all_pids, timeout)
    if not remaining:
        _clear_state()
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
    _clear_state()
    typer.echo("-> ADE services force-stopped.", err=True)


def _delegate_to(executable: str, ctx: typer.Context) -> None:
    args = list(ctx.args)
    if args and args[0] == ctx.info_name:
        args = args[1:]
    if not args:
        args = ["--help"]
    _run([executable, *args], cwd=REPO_ROOT)
