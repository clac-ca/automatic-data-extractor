"""Docker commands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import typer

from ade_cli.commands import common

DEFAULT_IMAGE = "ade-app:local"
DEFAULT_CONTAINER_PORT = 8000
DEFAULT_ENV_FILE = ".env"
DEFAULT_DATA_DIR = "data"
CONTAINER_DATA_DIR = "/app/data"

HELP_TEXT = (
    "Local Docker helpers with shortcuts for the ADE image.\n\n"
    "Shortcuts:\n"
    "  ade docker build [--image TAG]\n"
    "  ade docker run [--image TAG]\n"
    "  ade docker api [--image TAG]\n"
    "  ade docker worker [--image TAG]\n"
    "  ade docker shell [--image TAG]\n\n"
    "Other commands are passed through to the native `docker` CLI and run from the repo root.\n"
    "You can also use `ade docker -- <docker args>` for explicit passthrough.\n\n"
    "Examples:\n"
    "  ade docker build\n"
    "  ade docker run\n"
    "  ade docker -- ps\n"
)

PASSTHROUGH_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


def _docker_bin() -> str:
    """Return docker binary path with a friendly error if missing."""

    return common.require_command(
        "docker",
        friendly_name="docker",
        fix_hint="Install Docker Desktop/Engine and ensure the `docker` CLI is on your PATH.",
    )


def _abort(message: str, *, code: int = 2) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _parse_args(parser: argparse.ArgumentParser, args: list[str]) -> argparse.Namespace:
    try:
        parsed, unknown = parser.parse_known_args(args)
    except SystemExit as exc:  # argparse uses SystemExit for --help
        raise typer.Exit(code=exc.code)
    if unknown:
        unknown_display = " ".join(unknown)
        _abort(
            "Unsupported arguments for this shortcut.\n"
            f"Got: {unknown_display}\n"
            "Use `ade docker -- <args>` for full docker passthrough."
        )
    return parsed


def _resolve_image(image: str | None) -> str:
    return image or os.environ.get("ADE_IMAGE") or DEFAULT_IMAGE


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = common.REPO_ROOT / path
    return path


def _read_api_port(env_file: Path | None) -> int | None:
    if env_file is None:
        return None
    values = common.load_dotenv(env_file)
    raw = values.get("ADE_API_PORT")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        typer.echo(
            f"⚠️  Invalid ADE_API_PORT in {env_file}; defaulting to {DEFAULT_CONTAINER_PORT}.",
            err=True,
        )
        return None


def _resolve_env_file(env_file: str | None, *, no_env_file: bool) -> Path | None:
    if no_env_file:
        return None
    env_path = _resolve_path(env_file or DEFAULT_ENV_FILE)
    if not env_path.exists():
        _abort(
            f"❌ Env file not found: {env_path}\n"
            "Create one from .env.example or pass --no-env-file to skip.",
            code=1,
        )
    return env_path


def _resolve_data_dir(data_dir: str | None, *, no_data_dir: bool) -> Path | None:
    if no_data_dir:
        return None
    data_path = _resolve_path(data_dir or DEFAULT_DATA_DIR)
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
    return data_path


def _resolve_host_port(
    *,
    port: int | None,
    no_port: bool,
    map_port_by_default: bool,
    container_port: int,
) -> int | None:
    if no_port:
        return None
    if port is not None:
        return port
    if map_port_by_default:
        return container_port
    return None


def _build_image(
    docker_bin: str,
    args: list[str],
    *,
    prog: str = "ade docker build",
    description: str = "Build the ADE production image with sensible defaults.",
) -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
    )
    parser.add_argument(
        "--image",
        "-t",
        "--tag",
        dest="image",
        help="Image tag to build (default: ADE_IMAGE or ade-app:local).",
    )
    parser.add_argument("--context", default=".", help="Build context directory (default: .).")
    parser.add_argument("-f", "--file", dest="dockerfile", help="Path to Dockerfile (default: Dockerfile).")
    parser.add_argument("--no-cache", action="store_true", help="Disable build cache.")
    parser.add_argument("--pull", action="store_true", help="Always attempt to pull newer base images.")
    parser.add_argument("--platform", help="Target platform (passed to docker build).")

    parsed = _parse_args(parser, args)

    image = _resolve_image(parsed.image)
    context = parsed.context
    dockerfile = parsed.dockerfile

    cmd = [docker_bin, "build", "-t", image]
    if parsed.no_cache:
        cmd.append("--no-cache")
    if parsed.pull:
        cmd.append("--pull")
    if parsed.platform:
        cmd.extend(["--platform", parsed.platform])
    if dockerfile:
        cmd.extend(["-f", str(_resolve_path(dockerfile))])
    cmd.append(str(context))

    common.run(cmd, cwd=common.REPO_ROOT)


def _run_image(
    docker_bin: str,
    args: list[str],
    *,
    command: list[str] | None,
    map_port_by_default: bool,
    prog: str = "ade docker run-image",
    description: str = "Run the ADE image locally with sensible defaults (expects .env unless --no-env-file).",
    force_interactive: bool = False,
) -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
    )
    parser.add_argument(
        "--image",
        dest="image",
        help="Image tag to run (default: ADE_IMAGE or ade-app:local).",
    )
    parser.add_argument("--env-file", dest="env_file", help="Path to .env file (default: .env).")
    parser.add_argument("--no-env-file", action="store_true", help="Do not pass --env-file.")
    parser.add_argument("--data-dir", dest="data_dir", help="Host data dir to mount (default: ./data).")
    parser.add_argument("--no-data-dir", action="store_true", help="Do not mount a data directory.")
    parser.add_argument("-p", "--port", dest="port", type=int, help="Host port to publish.")
    parser.add_argument("--no-port", action="store_true", help="Do not publish the API port.")
    parser.add_argument("--name", help="Container name.")
    parser.add_argument("-d", "--detach", action="store_true", help="Run container in background.")
    parser.add_argument("--no-rm", action="store_true", help="Do not remove the container on exit.")

    parsed = _parse_args(parser, args)

    if force_interactive and parsed.detach:
        _abort("Cannot use --detach with this shortcut. Remove --detach or use `ade docker run ...`.", code=1)

    image = _resolve_image(parsed.image)
    env_file = _resolve_env_file(parsed.env_file, no_env_file=parsed.no_env_file)
    data_dir = _resolve_data_dir(parsed.data_dir, no_data_dir=parsed.no_data_dir)

    container_port = _read_api_port(env_file) or DEFAULT_CONTAINER_PORT
    host_port = _resolve_host_port(
        port=parsed.port,
        no_port=parsed.no_port,
        map_port_by_default=map_port_by_default,
        container_port=container_port,
    )

    cmd = [docker_bin, "run"]
    if not parsed.no_rm:
        cmd.append("--rm")
    if parsed.detach:
        cmd.append("-d")
    if force_interactive or not parsed.detach:
        cmd.append("-it")
    if parsed.name:
        cmd.extend(["--name", parsed.name])
    if env_file is not None:
        cmd.extend(["--env-file", str(env_file)])
    if data_dir is not None:
        cmd.extend(["-e", f"ADE_DATA_DIR={CONTAINER_DATA_DIR}"])
    if host_port is not None:
        cmd.extend(["-p", f"{host_port}:{container_port}"])
    if data_dir is not None:
        cmd.extend(["-v", f"{data_dir}:{CONTAINER_DATA_DIR}"])
    cmd.append(image)
    if command:
        cmd.extend(command)

    common.run(cmd, cwd=common.REPO_ROOT)


def docker_passthrough(ctx: typer.Context) -> None:
    """Pass-through to the system `docker` CLI (with ADE shortcuts)."""
    common.refresh_paths()
    docker_bin = _docker_bin()

    args = list(ctx.args)
    if not args:
        common.run([docker_bin], cwd=common.REPO_ROOT)
        return

    if args[0] == "--":
        passthrough = args[1:]
        if not passthrough:
            common.run([docker_bin], cwd=common.REPO_ROOT)
            return
        common.run([docker_bin, *passthrough], cwd=common.REPO_ROOT)
        return

    shortcut = args[0]
    rest = args[1:]

    if shortcut in {"build", "build-image"}:
        _build_image(
            docker_bin,
            rest,
            prog=f"ade docker {shortcut}",
            description="Build the ADE production image with sensible defaults.",
        )
        return
    if shortcut in {"run", "run-image"}:
        _run_image(
            docker_bin,
            rest,
            command=None,
            map_port_by_default=True,
            prog=f"ade docker {shortcut}",
            description="Run the ADE image locally with sensible defaults (expects .env unless --no-env-file).",
        )
        return
    if shortcut in {"api", "run-api"}:
        _run_image(
            docker_bin,
            rest,
            command=["api", "start"],
            map_port_by_default=True,
            prog=f"ade docker {shortcut}",
            description="Run the ADE image with the API only (expects .env unless --no-env-file).",
        )
        return
    if shortcut in {"worker", "run-worker"}:
        _run_image(
            docker_bin,
            rest,
            command=["worker", "start"],
            map_port_by_default=False,
            prog=f"ade docker {shortcut}",
            description="Run the ADE image with the worker only (expects .env unless --no-env-file).",
        )
        return
    if shortcut == "shell":
        _run_image(
            docker_bin,
            rest,
            command=["bash"],
            map_port_by_default=False,
            prog=f"ade docker {shortcut}",
            description="Open a shell in the ADE image (expects .env unless --no-env-file).",
            force_interactive=True,
        )
        return

    cmd = [docker_bin, *args]
    common.run(cmd, cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    """Register the docker command on the main CLI."""
    app.command(
        "docker",
        help=HELP_TEXT,
        no_args_is_help=False,
        context_settings=PASSTHROUGH_SETTINGS,
    )(docker_passthrough)
