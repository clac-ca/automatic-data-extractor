"""Launch the ADE server from the CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.main import DEFAULT_FRONTEND_DIR, start as start_application

CLIArgs = argparse.Namespace

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000


def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach command-line options for the `ade start` command."""

    host_default = os.getenv("ADE_SERVER_HOST", DEFAULT_HOST)
    try:
        port_default = int(os.getenv("ADE_SERVER_PORT", str(DEFAULT_PORT)))
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


def start(args: CLIArgs) -> None:
    """Run the ADE FastAPI application."""

    env_overrides = _parse_env_pairs(getattr(args, "env", []))

    start_application(
        host=str(getattr(args, "host")),
        port=int(getattr(args, "port")),
        reload=bool(getattr(args, "reload", True)),
        rebuild_frontend=bool(getattr(args, "rebuild_frontend", False)),
        frontend_dir=getattr(args, "frontend_dir", None),
        npm_command=getattr(args, "npm_command", None),
        env_overrides=env_overrides,
    )


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


__all__ = [
    "register_arguments",
    "start",
]
