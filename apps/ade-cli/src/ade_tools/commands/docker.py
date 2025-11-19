"""Docker commands."""

from __future__ import annotations

import typer

from ade_tools.commands import common

docker_app = typer.Typer(
    help="Docker helpers for the ADE stack (docker compose).",
    no_args_is_help=True,
)


@docker_app.command("up", help="Build and run the local Docker stack.")
def docker_up(
    detach: bool = typer.Option(
        True,
        "--detach/--no-detach",
        "-d",
        help="Run docker compose in detached mode.",
    ),
    build: bool = typer.Option(
        True,
        "--build/--no-build",
        help="Build images before starting containers.",
    ),
) -> None:
    """Start the ADE stack via docker compose."""
    common.refresh_paths()
    common.ensure_compose_file()
    cmd = ["docker", "compose", "-f", str(common.COMPOSE_FILE), "up"]
    if build:
        cmd.append("--build")
    if detach:
        cmd.append("-d")
    common.run(cmd, cwd=common.REPO_ROOT)


@docker_app.command("down", help="Stop the local Docker stack.")
def docker_down(
    volumes: bool = typer.Option(
        False,
        "--volumes",
        "-v",
        help="Also remove named volumes.",
    ),
) -> None:
    """Stop the ADE stack and optionally remove volumes."""
    common.refresh_paths()
    common.ensure_compose_file()
    cmd = ["docker", "compose", "-f", str(common.COMPOSE_FILE), "down"]
    if volumes:
        cmd.append("--volumes")
    common.run(cmd, cwd=common.REPO_ROOT)


@docker_app.command("logs", help="Tail docker compose logs.")
def docker_logs(
    service: str | None = typer.Argument(
        None,
        help="Optional service name to filter logs (e.g., 'api').",
    ),
    follow: bool = typer.Option(
        True,
        "--follow/--no-follow",
        "-f",
        help="Stream logs (follow).",
    ),
    tail: int = typer.Option(
        100,
        "--tail",
        help="Number of lines to show from the end of the logs.",
    ),
) -> None:
    """Tail logs for the ADE stack, optionally for a single service."""
    common.refresh_paths()
    common.ensure_compose_file()
    cmd = ["docker", "compose", "-f", str(common.COMPOSE_FILE), "logs", "--tail", str(tail)]
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)
    common.run(cmd, cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    """Register the docker subcommands on the main CLI."""
    app.add_typer(docker_app, name="docker")
