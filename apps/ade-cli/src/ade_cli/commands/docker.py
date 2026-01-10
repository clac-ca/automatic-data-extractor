"""Docker commands."""

from __future__ import annotations

import typer

from ade_cli.commands import common

HELP_TEXT = (
    "Thin wrapper around the native `docker` CLI.\n\n"
    "This command forwards all arguments to `docker` and runs from the repo root.\n\n"
    "Examples:\n"
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


def docker_passthrough(ctx: typer.Context) -> None:
    """Pass-through to the system `docker` CLI."""
    common.refresh_paths()
    docker_bin = _docker_bin()

    args = list(ctx.args)
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
