"""Docker commands."""

from __future__ import annotations

import typer

from ade_cli.commands import common

HELP_TEXT = (
    "Thin wrapper around the native `docker` CLI.\n\n"
    "This command forwards all arguments to `docker` and runs from the repo root.\n"
    "If the first argument is `compose` and you did not provide `-f/--file`, ADE injects\n"
    "the repo's `compose.yaml` automatically.\n\n"
    "Examples:\n"
    "  ade docker compose up -d --build\n"
    "  ade docker compose logs -f --tail=200 ade\n"
    "  ade docker build -t ade:local .\n"
    "  ade docker run --rm -p 8000:8000 ade:local\n"
)

PASSTHROUGH_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


def _docker_bin() -> str:
    """Return docker binary path with a friendly error if missing."""

    return common.require_command(
        "docker",
        friendly_name="docker",
        fix_hint="Install Docker Desktop/Engine and ensure the `docker` CLI is on your PATH.",
    )


def _inject_compose_file(args: list[str]) -> tuple[list[str], bool]:
    """Inject `-f compose.yaml` for `docker compose` unless the user already supplied `-f/--file`."""

    if not args or args[0] != "compose":
        return args, False

    if any(token in {"-f", "--file"} for token in args[1:]):
        return args, False

    common.ensure_compose_file()
    return ["compose", "-f", str(common.COMPOSE_FILE), *args[1:]], True


def docker_passthrough(ctx: typer.Context) -> None:
    """Pass-through to the system `docker` CLI, with ADE defaults for `docker compose`."""
    common.refresh_paths()
    docker_bin = _docker_bin()

    args = list(ctx.args)
    args, _ = _inject_compose_file(args)
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
