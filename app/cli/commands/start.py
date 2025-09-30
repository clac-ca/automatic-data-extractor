"""Launch the ADE FastAPI server with optional frontend build."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FRONTEND_DIR = ROOT_DIR / "frontend"
STATIC_DIR = ROOT_DIR / "app" / "static"
DIST_DIR_NAME = "dist"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000


def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach command-line options for the `ade start` command."""

    host_default = os.getenv("ADE_SERVER_HOST", DEFAULT_HOST)
    try:
        port_default = int(os.getenv("ADE_SERVER_PORT", DEFAULT_PORT))
    except ValueError:
        port_default = DEFAULT_PORT

    parser.add_argument(
        "--host",
        default=host_default,
        help=f"Host interface for uvicorn (default: {host_default}).",
    )
    parser.add_argument(
        "--port",
        default=port_default,
        type=int,
        help=f"Port for uvicorn to bind (default: {port_default}).",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable auto-reload. Reload is enabled by default for development.",
    )
    parser.add_argument(
        "--rebuild-frontend",
        action="store_true",
        help="Run the Vite production build and copy assets into app/static before starting.",
    )
    parser.add_argument(
        "--frontend-dir",
        type=Path,
        default=DEFAULT_FRONTEND_DIR,
        help="Path to the frontend project (default: <repo>/frontend).",
    )
    parser.add_argument(
        "--npm",
        dest="npm_command",
        default=None,
        help="Override the npm executable used for frontend builds (default: auto-detected).",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Set environment variables for the server process. Repeat the flag to provide multiple entries"
            " (e.g. --env ADE_LOGGING_LEVEL=DEBUG)."
        ),
    )
    parser.set_defaults(reload=True)


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


def _resolve_npm_command(override: str | None) -> str:
    if override:
        return override
    return "npm.cmd" if os.name == "nt" else "npm"


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    description: str,
) -> None:
    try:
        subprocess.run(command, cwd=str(cwd), env=env, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - depends on local tooling
        raise ValueError(f"{command[0]!r} is not available on PATH. Install the required tooling.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"{description} failed with exit code {exc.returncode}.") from exc


def _ensure_frontend_dependencies(
    *,
    frontend_dir: Path,
    npm_command: str,
    env: dict[str, str],
) -> None:
    if (frontend_dir / "node_modules").exists():
        return
    print("Installing frontend dependencies (npm install)...")
    _run_command(
        [npm_command, "install"],
        cwd=frontend_dir,
        env=env,
        description="npm install",
    )


def _clean_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for entry in path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _copy_frontend_build(frontend_dir: Path) -> None:
    dist_dir = frontend_dir / DIST_DIR_NAME
    if not dist_dir.exists() or not dist_dir.is_dir():
        raise ValueError(f"Frontend build output not found at {dist_dir}")

    _clean_directory(STATIC_DIR)
    shutil.copytree(dist_dir, STATIC_DIR, dirs_exist_ok=True)


def _build_frontend_assets(
    *,
    frontend_dir: Path,
    npm_command: str,
    env: dict[str, str],
) -> None:
    print("Building frontend bundle...")
    _ensure_frontend_dependencies(frontend_dir=frontend_dir, npm_command=npm_command, env=env)

    build_command = [npm_command, "run", "build"]
    _run_command(
        build_command,
        cwd=frontend_dir,
        env=env,
        description="npm run build",
    )

    print("Copying frontend assets into app/static...")
    _copy_frontend_build(frontend_dir)


def _print_banner(*, host: str, port: int, reload: bool, built: bool) -> None:
    headline = "ADE application server"
    separator = "-" * len(headline)
    url = f"http://{host}:{port}"
    print(headline)
    print(separator)
    print(f"Listening on {url}")
    print(f"Reload: {'enabled' if reload else 'disabled'}")
    if built:
        print("Frontend: rebuilt and synced to app/static")
    else:
        print("Frontend: serving existing assets from app/static")
    print("Press Ctrl+C to stop.\n")


def start(args: argparse.Namespace) -> None:
    """Run the ADE FastAPI application."""

    env_overrides = _parse_env_pairs(getattr(args, "env", []))
    for key, value in env_overrides.items():
        os.environ[key] = value

    os.environ.setdefault("ADE_SERVER_HOST", args.host)
    os.environ.setdefault("ADE_SERVER_PORT", str(args.port))
    os.environ.setdefault("ADE_SERVER_PUBLIC_URL", f"http://{args.host}:{args.port}")

    frontend_built = False
    if getattr(args, "rebuild_frontend", False):
        npm_command = _resolve_npm_command(getattr(args, "npm_command", None))
        frontend_dir: Path = getattr(args, "frontend_dir")
        frontend_dir = frontend_dir.expanduser().resolve()
        if not frontend_dir.exists() or not frontend_dir.is_dir():
            raise ValueError(f"Frontend directory not found at {frontend_dir}")

        env = os.environ.copy()
        _build_frontend_assets(frontend_dir=frontend_dir, npm_command=npm_command, env=env)
        frontend_built = True

    reload_enabled = getattr(args, "reload", True)
    _print_banner(host=args.host, port=args.port, reload=reload_enabled, built=frontend_built)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=reload_enabled,
        factory=False,
    )


__all__ = [
    "register_arguments",
    "start",
]
