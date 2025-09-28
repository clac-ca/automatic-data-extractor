"""Development server orchestration command."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import ctypes
except ImportError:  # pragma: no cover - fallback for restricted envs
    ctypes = None  # type: ignore[assignment]

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"

RESET = "\033[0m"
COLORS = {
    "backend": "\033[36m",  # cyan
    "frontend": "\033[35m",  # magenta
}


@dataclass
class ProcessSpec:
    label: str
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None


DEFAULT_BACKEND_HOST = "localhost"
DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_HOST = "localhost"
DEFAULT_FRONTEND_PORT = 5173


def _resolve_backend_public_url(args: argparse.Namespace, overrides: dict[str, str]) -> str:
    candidate = (
        overrides.get("ADE_SERVER_PUBLIC_URL")
        or os.getenv("ADE_SERVER_PUBLIC_URL")
        or ""
    ).strip()
    if candidate:
        return candidate
    return f"http://{args.backend_host}:{args.backend_port}"


def _resolve_vite_api_base_url(args: argparse.Namespace, overrides: dict[str, str]) -> str:
    explicit = (args.vite_api_base_url or os.getenv("VITE_API_BASE_URL") or "").strip()
    if explicit:
        return explicit
    return _resolve_backend_public_url(args, overrides)


def _compose_frontend_env(args: argparse.Namespace, overrides: dict[str, str]) -> dict[str, str]:
    env = overrides.copy()
    env.setdefault("VITE_API_BASE_URL", _resolve_vite_api_base_url(args, overrides))
    return env


def _parse_env_pairs(pairs: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for entry in pairs:
        if "=" not in entry:
            raise ValueError(f"Invalid --env value '{entry}'. Use KEY=VALUE format.")
        key, value = entry.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Environment variable name cannot be empty.")
        env[key] = value
    return env



def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach command-line options for the `ade start` workflow."""

    backend_host_default = os.getenv("ADE_SERVER_HOST", DEFAULT_BACKEND_HOST)
    try:
        backend_port_default = int(os.getenv("ADE_SERVER_PORT", DEFAULT_BACKEND_PORT))
    except ValueError:
        backend_port_default = DEFAULT_BACKEND_PORT
    frontend_host_default = DEFAULT_FRONTEND_HOST
    frontend_port_default = DEFAULT_FRONTEND_PORT

    parser.add_argument(
        "--skip-backend",
        action="store_true",
        help="Do not launch the FastAPI development server.",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Do not launch the Vite development server.",
    )
    parser.add_argument(
        "--backend-host",
        default=backend_host_default,
        help=f"Host interface for uvicorn (default: {backend_host_default}).",
    )
    parser.add_argument(
        "--backend-port",
        default=backend_port_default,
        type=int,
        help=f"Port for uvicorn to bind (default: {backend_port_default}).",
    )
    parser.add_argument(
        "--frontend-host",
        default=frontend_host_default,
        help=f"Host interface for the Vite dev server (default: {frontend_host_default}).",
    )
    parser.add_argument(
        "--frontend-port",
        default=frontend_port_default,
        type=int,
        help=f"Port for the Vite dev server (default: {frontend_port_default}).",
    )
    parser.add_argument(
        "--vite-api-base-url",
        dest="vite_api_base_url",
        default=None,
        help="Override the Vite dev server VITE_API_BASE_URL environment variable.",
    )
    parser.add_argument(
        "--vite-api-url",
        dest="vite_api_base_url",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Set environment variables for the spawned servers. Repeat the flag "
            "to pass multiple entries (e.g. --env ADE_LOGGING_LEVEL=INFO)."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in aggregated output.",
    )

def _build_specs(
    args: argparse.Namespace,
    *,
    npm_command: str,
    env_overrides: dict[str, str],
) -> list[ProcessSpec]:
    specs: list[ProcessSpec] = []

    if not args.skip_backend:
        backend_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.main:app",
            "--reload",
            "--host",
            args.backend_host,
            "--port",
            str(args.backend_port),
        ]
        backend_env = env_overrides.copy() if env_overrides else None
        specs.append(ProcessSpec("backend", backend_cmd, ROOT_DIR, env=backend_env))

    if not args.skip_frontend:
        frontend_cmd = [
            npm_command,
            "run",
            "dev",
            "--",
            "--host",
            args.frontend_host,
            "--port",
            str(args.frontend_port),
        ]
        env = _compose_frontend_env(args, env_overrides)
        specs.append(ProcessSpec("frontend", frontend_cmd, FRONTEND_DIR, env=env))

    return specs

def _ensure_frontend_dependencies(frontend_dir: Path, npm_command: str) -> None:
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        return

    print("Installing frontend dependencies (npm install)...")
    try:
        subprocess.run(
            [npm_command, "install"],
            cwd=str(frontend_dir),
            check=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on local env
        raise ValueError(
            "npm is not available on PATH. Install Node.js 20 LTS before running `ade start`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("`npm install` failed. Review the output above for details.") from exc


def _enable_windows_ansi() -> None:
    if os.name != "nt" or ctypes is None:  # pragma: no cover - Windows only
        return
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()  # type: ignore[attr-defined]
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


def _should_use_color(disable_color: bool) -> bool:
    if disable_color:
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt" and ctypes is None:
        return False
    return True


def _colorize(label: str, text: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    color = COLORS.get(label)
    if not color:
        return text
    return f"{color}{text}{RESET}"


def _print_banner(
    *,
    backend_host: str,
    backend_port: int,
    backend_public_url: str,
    frontend_host: str,
    frontend_port: int,
    vite_api_base_url: str,
    color: bool,
) -> None:
    headline = "ADE development servers"
    separator = "-" * len(headline)
    backend_bind = f"{backend_host}:{backend_port}"
    frontend_url = f"http://{frontend_host}:{frontend_port}"

    backend_label = _colorize("backend", "Backend", enabled=color)
    frontend_label = _colorize("frontend", "Frontend", enabled=color)

    print(headline)
    print(separator)
    print(f"{backend_label}: bind {backend_bind}  (uvicorn --reload)")
    print(f"           public {backend_public_url}")
    print(f"{frontend_label}: {frontend_url}  (Vite hot module reload)")
    if vite_api_base_url:
        print(f"Vite API base: {vite_api_base_url}")
    print("Stop with Ctrl+C. Use --help for more flags.\n")

def _launch_process(spec: ProcessSpec, *, color_enabled: bool) -> tuple[str, subprocess.Popen[str]]:
    env = os.environ.copy()
    if spec.env:
        env.update(spec.env)

    proc = subprocess.Popen(
        spec.command,
        cwd=str(spec.cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    proc._ade_color = color_enabled  # type: ignore[attr-defined]
    return spec.label, proc


def _stream_output(label: str, proc: subprocess.Popen[str]) -> None:
    color_enabled = getattr(proc, "_ade_color", False)
    prefix = _colorize(label, f"[{label}] ", enabled=color_enabled)
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line if line.endswith("\n") else f"{line}\n"
        sys.stdout.write(prefix + text)
        sys.stdout.flush()
    proc.stdout.close()


def _stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def start(args: argparse.Namespace) -> None:
    """Launch the backend and frontend development servers."""

    npm_command = "npm.cmd" if os.name == "nt" else "npm"
    env_overrides = _parse_env_pairs(getattr(args, "env", []))
    if (
        "ADE_SERVER_HOST" not in env_overrides
        and "ADE_SERVER_HOST" not in os.environ
    ):
        env_overrides["ADE_SERVER_HOST"] = args.backend_host
    if (
        "ADE_SERVER_PORT" not in env_overrides
        and "ADE_SERVER_PORT" not in os.environ
    ):
        env_overrides["ADE_SERVER_PORT"] = str(args.backend_port)
    if (
        "ADE_SERVER_PUBLIC_URL" not in env_overrides
        and "ADE_SERVER_PUBLIC_URL" not in os.environ
    ):
        env_overrides["ADE_SERVER_PUBLIC_URL"] = (
            f"http://{args.backend_host}:{args.backend_port}"
        )
    if not args.skip_frontend:
        _ensure_frontend_dependencies(FRONTEND_DIR, npm_command)

    specs = _build_specs(args, npm_command=npm_command, env_overrides=env_overrides)
    if not specs:
        raise ValueError("Nothing to start. Remove --skip options to launch a server.")

    use_color = _should_use_color(args.no_color)
    if use_color and os.name == "nt":
        _enable_windows_ansi()

    backend_public_url = _resolve_backend_public_url(args, env_overrides)
    api_base_url = env_overrides.get("VITE_API_BASE_URL") or _resolve_vite_api_base_url(
        args, env_overrides
    )

    _print_banner(
        backend_host=args.backend_host,
        backend_port=args.backend_port,
        backend_public_url=backend_public_url,
        frontend_host=args.frontend_host,
        frontend_port=args.frontend_port,
        vite_api_base_url=api_base_url,
        color=use_color,
    )

    processes: list[tuple[str, subprocess.Popen[str]]] = []
    for spec in specs:
        processes.append(_launch_process(spec, color_enabled=use_color))

    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    for label, proc in processes:
        thread = threading.Thread(target=_stream_output, args=(label, proc), daemon=True)
        thread.start()
        threads.append(thread)

    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)

    def _handle_signal(signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    exit_code = 0
    try:
        while not stop_event.is_set():
            for label, proc in processes:
                code = proc.poll()
                if code is not None:
                    if code != 0:
                        print(f"{label} exited with status {code}")
                        exit_code = code
                    stop_event.set()
                    break
            time.sleep(0.2)
    finally:
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
        for _, proc in processes:
            _stop_process(proc)
        for thread in threads:
            thread.join(timeout=1)

    if exit_code != 0:
        raise SystemExit(exit_code)
