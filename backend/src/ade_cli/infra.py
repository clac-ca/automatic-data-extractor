"""`ade infra` command implementations."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from paths import REPO_ROOT

from .common import require_command, run
from .local_dev import ensure_local_env

PASSTHROUGH_CONTEXT_SETTINGS = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
}
INFRA_COMPOSE_FILE = REPO_ROOT / "docker-compose.infra.yaml"

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Local infrastructure CLI (Postgres + Azurite).",
)


def _docker_preflight() -> None:
    docker = require_command(
        "docker",
        friendly_name="docker",
        fix_hint="Install Docker Desktop/Engine and ensure `docker` is available on PATH.",
    )
    completed = subprocess.run(
        [docker, "info"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return

    message = completed.stderr.strip() or completed.stdout.strip()
    typer.echo("error: Docker daemon is not reachable.", err=True)
    if message:
        typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _compose_base_args(*, project_name: str, env_file: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        "--env-file",
        str(env_file),
        "-f",
        str(INFRA_COMPOSE_FILE),
    ]


def _run_compose(
    *,
    subcommand: str,
    extra_args: list[str],
    force: bool = False,
) -> None:
    result = ensure_local_env(force=force)
    project_name = result.values.get("COMPOSE_PROJECT_NAME", result.profile.project_name)

    if result.wrote_file:
        typer.echo(f"-> wrote local profile: {result.path.relative_to(REPO_ROOT)}", err=True)

    cmd = _compose_base_args(project_name=project_name, env_file=result.path)
    cmd.append(subcommand)
    cmd.extend(extra_args)
    run(cmd, cwd=REPO_ROOT)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(
    name="up",
    help="Start local infrastructure (supports the same flags as `docker compose up`).",
    context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
)
def up(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Regenerate .env local profile keys with deterministic defaults "
            "before starting infra."
        ),
    ),
) -> None:
    _docker_preflight()
    _run_compose(
        subcommand="up",
        extra_args=list(ctx.args),
        force=force,
    )


@app.command(
    name="down",
    help="Stop and remove local infrastructure resources.",
    context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
)
def down(ctx: typer.Context) -> None:
    _docker_preflight()
    _run_compose(subcommand="down", extra_args=list(ctx.args))


@app.command(
    name="ps",
    help="Show infrastructure service status.",
    context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
)
def ps(ctx: typer.Context) -> None:
    _docker_preflight()
    _run_compose(subcommand="ps", extra_args=list(ctx.args))


@app.command(
    name="logs",
    help="Stream infrastructure logs.",
    context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
)
def logs(ctx: typer.Context) -> None:
    _docker_preflight()
    _run_compose(subcommand="logs", extra_args=list(ctx.args))


@app.command(
    name="config",
    help="Render resolved docker compose config for local infrastructure.",
    context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
)
def config(ctx: typer.Context) -> None:
    _docker_preflight()
    _run_compose(subcommand="config", extra_args=list(ctx.args))


@app.command(name="info", help="Show local profile details for this worktree.")
def info() -> None:
    result = ensure_local_env(force=False)
    values = result.values
    project_name = values.get("COMPOSE_PROJECT_NAME", result.profile.project_name)
    db_port = values.get("ADE_LOCAL_DB_PORT", str(result.profile.db_port))
    blob_port = values.get("ADE_LOCAL_BLOB_PORT", str(result.profile.blob_port))
    web_port = values.get("ADE_WEB_PORT", str(result.profile.web_port))
    api_port = values.get("ADE_API_PORT", str(result.profile.api_port))
    typer.echo(f"Local profile file: {result.path}")
    typer.echo(f"Compose project:   {project_name}")
    typer.echo(f"Web URL:           http://127.0.0.1:{web_port}")
    typer.echo(f"API URL:           http://127.0.0.1:{api_port}")
    typer.echo(f"Postgres port:     {db_port}")
    typer.echo(f"Blob port:         {blob_port}")
    typer.echo(f"Profile id:        {result.profile.profile_id}")


__all__ = ["app"]
