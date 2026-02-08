"""`ade web` command implementations."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import typer

from paths import FRONTEND_DIR, REPO_ROOT

from .common import require_command, run

DEFAULT_INTERNAL_API_URL = "http://localhost:8001"
DEFAULT_PUBLIC_WEB_URL = "http://127.0.0.1:8000"

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Web CLI (frontend).",
)


def _npm_cmd(*args: str) -> list[str]:
    return ["npm", "--prefix", str(FRONTEND_DIR), *args]


def _resolve_internal_api_url(env: dict[str, str]) -> str:
    raw = env.get("ADE_INTERNAL_API_URL", DEFAULT_INTERNAL_API_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        typer.echo(
            "error: ADE_INTERNAL_API_URL must be an origin like http://localhost:8001.",
            err=True,
        )
        raise typer.Exit(code=1)
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        typer.echo(
            "error: ADE_INTERNAL_API_URL must not include a path/query/fragment (no /api).",
            err=True,
        )
        raise typer.Exit(code=1)
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_public_web_url(env: dict[str, str]) -> str:
    raw_public = env.get("ADE_PUBLIC_WEB_URL", "").strip().rstrip("/")
    if raw_public:
        parsed = urlparse(raw_public)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
                typer.echo(
                    "warning: ADE_PUBLIC_WEB_URL includes a path/query/fragment; ignoring it.",
                    err=True,
                )
            return f"{parsed.scheme}://{parsed.netloc}"
        typer.echo(
            "warning: ADE_PUBLIC_WEB_URL must be a full origin "
            "(for example http://127.0.0.1:8000); "
            "falling back to ADE_WEB_PORT.",
            err=True,
        )

    raw_port = env.get("ADE_WEB_PORT", "").strip()
    if raw_port:
        if raw_port.isdigit() and 1 <= int(raw_port) <= 65535:
            return f"http://127.0.0.1:{raw_port}"
        typer.echo("error: ADE_WEB_PORT must be an integer between 1 and 65535.", err=True)
        raise typer.Exit(code=1)

    return DEFAULT_PUBLIC_WEB_URL


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="start", help="Serve built frontend via nginx.")
def start() -> None:
    env = os.environ.copy()
    env["ADE_INTERNAL_API_URL"] = _resolve_internal_api_url(env)
    nginx = require_command(
        "nginx",
        friendly_name="nginx",
        fix_hint="Install nginx and ensure it is available on PATH.",
    )
    run([nginx, "-g", "daemon off;"], cwd=REPO_ROOT, env=env)


@app.command(name="dev", help="Run Vite dev server.")
def dev() -> None:
    env = os.environ.copy()
    env["ADE_INTERNAL_API_URL"] = _resolve_internal_api_url(env)
    run(_npm_cmd("run", "dev"), cwd=REPO_ROOT, env=env)


@app.command(name="build", help="Build frontend assets.")
def build() -> None:
    run(_npm_cmd("run", "build"), cwd=REPO_ROOT)


@app.command(name="test", help="Run frontend tests.")
def test() -> None:
    run(_npm_cmd("run", "test"), cwd=REPO_ROOT)


@app.command(name="test:watch", help="Run frontend tests in watch mode.")
def test_watch() -> None:
    run(_npm_cmd("run", "test:watch"), cwd=REPO_ROOT)


@app.command(name="test:coverage", help="Run frontend tests with coverage.")
def test_coverage() -> None:
    run(_npm_cmd("run", "test:coverage"), cwd=REPO_ROOT)


@app.command(name="lint", help="Lint frontend code.")
def lint() -> None:
    run(_npm_cmd("run", "lint"), cwd=REPO_ROOT)


@app.command(name="typecheck", help="Typecheck frontend code.")
def typecheck() -> None:
    run(_npm_cmd("run", "typecheck"), cwd=REPO_ROOT)


@app.command(name="preview", help="Preview built frontend.")
def preview() -> None:
    run(_npm_cmd("run", "preview"), cwd=REPO_ROOT)


@app.command(name="open", help="Open web UI in the default browser.")
def open_web() -> None:
    url = resolve_public_web_url(os.environ)
    typer.echo(url)
    status = typer.launch(url)
    if status != 0:
        typer.echo(
            f"warning: failed to open browser automatically (exit code {status}).",
            err=True,
        )
        typer.echo(f"Open manually: {url}", err=True)


__all__ = ["app", "resolve_public_web_url"]
