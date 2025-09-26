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


def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach command-line options for the `ade start` workflow."""

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
        default="127.0.0.1",
        help="Host interface for uvicorn (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--backend-port",
        default=8000,
        type=int,
        help="Port for uvicorn to bind (default: 8000).",
    )
    parser.add_argument(
        "--frontend-host",
        default="127.0.0.1",
        help="Host interface for the Vite dev server (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--frontend-port",
        default=5173,
        type=int,
        help="Port for the Vite dev server (default: 5173).",
    )
    parser.add_argument(
        "--vite-api-url",
        help="Override the Vite dev server `VITE_API_URL` environment variable.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in aggregated output.",
    )


def _build_specs(args: argparse.Namespace) -> list[ProcessSpec]:
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
        specs.append(ProcessSpec("backend", backend_cmd, ROOT_DIR))

    if not args.skip_frontend:
        npm_command = "npm.cmd" if os.name == "nt" else "npm"
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
        env: dict[str, str] | None = None
        if args.vite_api_url:
            env = {"VITE_API_URL": args.vite_api_url}
        specs.append(ProcessSpec("frontend", frontend_cmd, FRONTEND_DIR, env=env))

    return specs


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
    frontend_host: str,
    frontend_port: int,
    vite_api_url: str | None,
    color: bool,
) -> None:
    headline = "ADE development servers"
    separator = "-" * len(headline)
    backend_url = f"http://{backend_host}:{backend_port}"
    frontend_url = f"http://{frontend_host}:{frontend_port}"

    backend_label = _colorize("backend", "Backend", enabled=color)
    frontend_label = _colorize("frontend", "Frontend", enabled=color)

    print(headline)
    print(separator)
    print(f"{backend_label}: {backend_url}  (uvicorn --reload)")
    print(f"{frontend_label}: {frontend_url}  (Vite hot module reload)")
    if vite_api_url:
        print(f"Vite API target: {vite_api_url}")
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
    setattr(proc, "_ade_color", color_enabled)
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

    specs = _build_specs(args)
    if not specs:
        raise ValueError("Nothing to start. Remove --skip options to launch a server.")

    use_color = _should_use_color(args.no_color)
    if use_color and os.name == "nt":
        _enable_windows_ansi()

    _print_banner(
        backend_host=args.backend_host,
        backend_port=args.backend_port,
        frontend_host=args.frontend_host,
        frontend_port=args.frontend_port,
        vite_api_url=args.vite_api_url,
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
