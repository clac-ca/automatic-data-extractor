"""`ade web` command group."""

from __future__ import annotations

import os

import typer

from .. import shared

web_app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Web CLI (frontend).",
)


@web_app.callback()
def web(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@web_app.command(name="start", help="Serve built frontend via nginx.")
def web_start() -> None:
    base_env = os.environ.copy()
    web_env = base_env.copy()
    web_env["ADE_INTERNAL_API_URL"] = shared._resolve_internal_api_url(base_env)
    shared._run(shared._nginx_cmd(), cwd=shared.REPO_ROOT, env=web_env)


@web_app.command(name="dev", help="Run Vite dev server.")
def web_dev() -> None:
    base_env = os.environ.copy()
    web_env = base_env.copy()
    web_env["ADE_INTERNAL_API_URL"] = shared._resolve_internal_api_url(base_env)
    shared._run(shared._npm_cmd("run", "dev"), cwd=shared.REPO_ROOT, env=web_env)


@web_app.command(name="build", help="Build frontend assets.")
def web_build() -> None:
    shared._run(shared._npm_cmd("run", "build"), cwd=shared.REPO_ROOT)


@web_app.command(name="test", help="Run frontend tests.")
def web_test() -> None:
    shared._run(shared._npm_cmd("run", "test"), cwd=shared.REPO_ROOT)


@web_app.command(name="test:watch", help="Run frontend tests in watch mode.")
def web_test_watch() -> None:
    shared._run(shared._npm_cmd("run", "test:watch"), cwd=shared.REPO_ROOT)


@web_app.command(name="test:coverage", help="Run frontend tests with coverage.")
def web_test_coverage() -> None:
    shared._run(shared._npm_cmd("run", "test:coverage"), cwd=shared.REPO_ROOT)


@web_app.command(name="lint", help="Lint frontend code.")
def web_lint() -> None:
    shared._run(shared._npm_cmd("run", "lint"), cwd=shared.REPO_ROOT)


@web_app.command(name="typecheck", help="Typecheck frontend code.")
def web_typecheck() -> None:
    shared._run(shared._npm_cmd("run", "typecheck"), cwd=shared.REPO_ROOT)


@web_app.command(name="preview", help="Preview built frontend.")
def web_preview() -> None:
    shared._run(shared._npm_cmd("run", "preview"), cwd=shared.REPO_ROOT)


def register(app: typer.Typer) -> None:
    app.add_typer(web_app, name="web")
