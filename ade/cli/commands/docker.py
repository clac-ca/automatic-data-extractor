"""Docker-focused CLI commands for ADE."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
from pathlib import Path

CLIArgs = argparse.Namespace

_DEFAULT_TAG = "ade:local"
_DEFAULT_CONTEXT = Path(".")
_DEFAULT_DOCKERFILE = Path("Dockerfile")
_DEFAULT_ENV_FILE = Path(".env")
_DEFAULT_HOST_PORT = 8000
_DEFAULT_CONTAINER_PORT = 8000


def _ensure_docker_available() -> None:
    if shutil.which("docker") is None:
        raise ValueError(
            "Docker CLI not found. Install Docker Desktop/Engine and ensure 'docker' is on PATH.",
        )


def _run_docker(command: list[str]) -> None:
    print(f"$ {shlex.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Docker command failed with exit code {exc.returncode}.") from exc


def _validate_path(path: Path, *, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"{description} not found at {resolved}")
    return resolved


def register_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach docker-focused subcommands to the ADE CLI."""

    subparsers = parser.add_subparsers(dest="docker_command", required=True)

    build_parser = subparsers.add_parser(
        "build",
        help="Build the ADE Docker image (wrapper around 'docker build').",
    )
    build_parser.add_argument(
        "--tag",
        default=_DEFAULT_TAG,
        help=f"Image tag to produce (default: {_DEFAULT_TAG}).",
    )
    build_parser.add_argument(
        "--context",
        default=str(_DEFAULT_CONTEXT),
        help="Docker build context directory (default: current directory).",
    )
    build_parser.add_argument(
        "--dockerfile",
        default=str(_DEFAULT_DOCKERFILE),
        help=f"Dockerfile path (default: {_DEFAULT_DOCKERFILE}).",
    )
    build_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable Docker's build cache (passes --no-cache).",
    )
    build_parser.add_argument(
        "--pull",
        action="store_true",
        help="Always attempt to pull newer base images before building.",
    )
    build_parser.add_argument(
        "--build-arg",
        dest="build_args",
        action="append",
        metavar="KEY=VALUE",
        help="Forward a build argument to Docker (repeatable).",
    )
    build_parser.set_defaults(handler=_handle_build)

    run_parser = subparsers.add_parser(
        "run",
        help="Run the ADE Docker image (wrapper around 'docker run').",
    )
    run_parser.add_argument(
        "--tag",
        default=_DEFAULT_TAG,
        help=f"Image tag to run (default: {_DEFAULT_TAG}).",
    )
    run_parser.add_argument(
        "--env-file",
        default=str(_DEFAULT_ENV_FILE),
        help=f"Path to env file passed via --env-file (default: {_DEFAULT_ENV_FILE}).",
    )
    run_parser.add_argument(
        "--env",
        dest="env",
        action="append",
        metavar="KEY=VALUE",
        help="Inline environment variable (repeatable).",
    )
    run_parser.add_argument(
        "--host-port",
        type=int,
        default=_DEFAULT_HOST_PORT,
        help=f"Host port to expose (default: {_DEFAULT_HOST_PORT}).",
    )
    run_parser.add_argument(
        "--container-port",
        type=int,
        default=_DEFAULT_CONTAINER_PORT,
        help=f"Container port to publish (default: {_DEFAULT_CONTAINER_PORT}).",
    )
    run_parser.add_argument(
        "--volume",
        action="append",
        metavar="HOST_PATH:CONTAINER_PATH",
        help="Mount a volume into the container (repeatable).",
    )
    run_parser.add_argument(
        "--name",
        help="Assign a name to the running container.",
    )
    run_parser.add_argument(
        "--detach",
        action="store_true",
        help="Run the container in detached mode (passes --detach).",
    )
    run_parser.add_argument(
        "--no-remove",
        action="store_true",
        help="Keep the container after it exits (omit --rm).",
    )
    run_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command override appended to docker run.",
    )
    run_parser.set_defaults(handler=_handle_run)


def _handle_build(args: CLIArgs) -> None:
    _ensure_docker_available()

    context = _validate_path(Path(args.context), description="Docker context")
    dockerfile = _validate_path(Path(args.dockerfile), description="Dockerfile")

    command: list[str] = [
        "docker",
        "build",
        "-t",
        args.tag,
        "-f",
        str(dockerfile),
    ]
    if args.no_cache:
        command.append("--no-cache")
    if args.pull:
        command.append("--pull")
    for build_arg in args.build_args or []:
        command.extend(["--build-arg", build_arg])
    command.append(str(context))
    _run_docker(command)


def _handle_run(args: CLIArgs) -> None:
    _ensure_docker_available()

    command: list[str] = ["docker", "run"]
    if not args.no_remove:
        command.append("--rm")
    if args.detach:
        command.append("--detach")
    if args.name:
        command.extend(["--name", args.name])

    if args.env_file:
        env_file = _validate_path(Path(args.env_file), description="Environment file")
        command.extend(["--env-file", str(env_file)])
    for env_pair in args.env or []:
        command.extend(["--env", env_pair])

    command.extend([
        "--publish",
        f"{args.host_port}:{args.container_port}",
    ])
    for volume in args.volume or []:
        command.extend(["--volume", volume])

    command.append(args.tag)

    if args.command:
        remainder = list(args.command)
        if remainder and remainder[0] == "--":
            remainder = remainder[1:]
        command.extend(remainder)

    _run_docker(command)


__all__ = ["register_arguments"]