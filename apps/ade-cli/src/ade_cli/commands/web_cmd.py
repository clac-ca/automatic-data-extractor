"""Web command group (npm forwarding)."""

from __future__ import annotations

import typer

from ade_cli.commands import common

app = typer.Typer(
    help="ADE web commands (dev, build, test, lint) forwarded to npm scripts.",
    invoke_without_command=True,
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _run_npm_script(script: str, extra: list[str] | None = None) -> None:
    common.refresh_paths()
    common.ensure_node_modules()
    npm_bin = common.npm_path()
    cmd = [npm_bin, "--prefix", str(common.FRONTEND_DIR), "run", script]
    if extra:
        cmd.extend(["--", *extra])
    common.run(cmd, cwd=common.REPO_ROOT)


@app.command(name="dev", help="Run the web dev server (Vite).")
def dev(
    host: str = typer.Option(None, "--host", help="Host/interface for the web dev server.", envvar="ADE_WEB_HOST"),
    port: int = typer.Option(None, "--port", help="Port for the web dev server.", envvar="ADE_WEB_PORT"),
) -> None:
    extra: list[str] = []
    if host:
        extra.extend(["--host", host])
    if port:
        extra.extend(["--port", str(port)])
    _run_npm_script("dev", extra)


@app.command(name="build", help="Build web assets.")
def build() -> None:
    _run_npm_script("build")


@app.command(name="test", help="Run web tests (npm test).")
def test() -> None:
    _run_npm_script("test")


@app.command(name="lint", help="Run web linting (npm run lint).")
def lint() -> None:
    _run_npm_script("lint")
