"""`ade-api` command implementations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from ade_api.settings import Settings
from paths import BACKEND_ROOT, FRONTEND_DIR, REPO_ROOT

from .common import TestSuite, parse_test_suite, require_command, run

DEFAULT_API_BIND_PORT = 8001
DEFAULT_DEV_PROCESSES = 1
DEV_RELOAD_DIRS = (
    "src",
    "tests/api",
    "tests/worker",
)


app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE API CLI (dev, start, test, lint, routes, types).",
)


def _ensure_node_modules(frontend_dir: Path | None = None) -> None:
    directory = frontend_dir or FRONTEND_DIR
    if not directory.exists():
        typer.echo("error: frontend directory missing; expected frontend/", err=True)
        raise typer.Exit(code=1)
    if not (directory / "package.json").exists():
        typer.echo("error: package.json missing in frontend/.", err=True)
        raise typer.Exit(code=1)
    if not (directory / "node_modules").exists():
        typer.echo(
            "error: frontend dependencies not installed (run `./setup.sh` from repo root).",
            err=True,
        )
        raise typer.Exit(code=1)


def run_dev(*, host: str | None = None, processes: int | None = None) -> None:
    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    processes = int(processes if processes is not None else DEFAULT_DEV_PROCESSES)

    env = os.environ.copy()
    env["ADE_API_PROCESSES"] = str(processes)

    if processes > 1:
        typer.echo("Note: API processes > 1; disabling reload in dev.")

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "ade_api.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        settings.effective_api_log_level.lower(),
    ]
    if not settings.access_log_enabled:
        api_cmd.append("--no-access-log")
    if processes == 1:
        api_cmd.append("--reload")
        for reload_dir in DEV_RELOAD_DIRS:
            api_cmd.extend(["--reload-dir", reload_dir])
    else:
        api_cmd.extend(["--workers", str(processes)])

    typer.echo(f"API dev server: http://{host}:{port}")
    run(api_cmd, cwd=BACKEND_ROOT, env=env)


def run_start(*, host: str | None = None, processes: int | None = None) -> None:
    settings = Settings()
    port = DEFAULT_API_BIND_PORT
    host = host or (settings.api_host or "0.0.0.0")
    processes = int(processes if processes is not None else (settings.api_processes or 1))

    env = os.environ.copy()
    env["ADE_API_PROCESSES"] = str(processes)

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "ade_api.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--loop",
        "uvloop",
        "--http",
        "httptools",
        "--log-level",
        settings.effective_api_log_level.lower(),
    ]
    if settings.api_proxy_headers_enabled:
        api_cmd.append("--proxy-headers")
        api_cmd.extend(["--forwarded-allow-ips", settings.api_forwarded_allow_ips])
    else:
        api_cmd.append("--no-proxy-headers")
    if not settings.access_log_enabled:
        api_cmd.append("--no-access-log")
    if processes > 1:
        api_cmd.extend(["--workers", str(processes)])

    typer.echo(f"Starting ADE API on http://{host}:{port}")
    run(api_cmd, env=env)


def run_tests(suite: TestSuite) -> None:
    api_tests = "tests/api"
    cmd = [sys.executable, "-m", "pytest", api_tests]
    if suite is not TestSuite.ALL:
        cmd.extend(["-m", suite.value])
    if suite is TestSuite.UNIT:
        cmd.extend(["--ignore", f"{api_tests}/integration"])
    run(cmd, cwd=BACKEND_ROOT)


def run_lint(fix: bool = False) -> None:
    ruff_cmd = [sys.executable, "-m", "ruff", "check", "src/ade_api"]
    if fix:
        ruff_cmd.append("--fix")
    run(ruff_cmd, cwd=BACKEND_ROOT)
    run([sys.executable, "-m", "mypy", "src/ade_api"], cwd=BACKEND_ROOT)


def run_routes() -> None:
    run([sys.executable, "-m", "ade_api.scripts.api_routes"], cwd=REPO_ROOT)


def run_types() -> None:
    """Generate OpenAPI JSON and TypeScript types for frontend."""

    openapi_path = BACKEND_ROOT / "src" / "ade_api" / "openapi.json"
    output_path = FRONTEND_DIR / "src" / "types" / "generated" / "openapi.d.ts"

    run(
        [
            sys.executable,
            "-m",
            "ade_api.scripts.generate_openapi",
            "--output",
            str(openapi_path),
        ],
        cwd=REPO_ROOT,
    )

    if not FRONTEND_DIR.exists():
        typer.echo("frontend missing; OpenAPI JSON generated only.")
        return

    _ensure_node_modules()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    require_command(
        npx_cmd,
        friendly_name="npx",
        fix_hint="Install Node.js (LTS) and run `npm install` in frontend.",
    )
    run(
        [
            npx_cmd,
            "openapi-typescript",
            str(openapi_path),
            "--output",
            str(output_path),
            "--export-type",
        ],
        cwd=FRONTEND_DIR,
    )
    typer.echo(f"generated {output_path.relative_to(REPO_ROOT)}")


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="dev", help="Run the API dev server only (apply migrations first).")
def dev(
    host: str | None = typer.Option(
        None,
        "--host",
        help="Host/interface for the API dev server.",
        envvar="ADE_API_HOST",
    ),
    processes: int | None = typer.Option(
        None,
        "--processes",
        help="Number of API processes (disables reload when > 1).",
        min=1,
    ),
) -> None:
    run_dev(host=host, processes=processes)


@app.command(name="start", help="Start the API server (requires migrations).")
def start(
    host: str | None = typer.Option(
        None,
        "--host",
        help="Host/interface for the API server.",
        envvar="ADE_API_HOST",
    ),
    processes: int | None = typer.Option(
        None,
        "--processes",
        help="Number of API processes.",
        envvar="ADE_API_PROCESSES",
        min=1,
    ),
) -> None:
    run_start(host=host, processes=processes)


@app.command(name="test", help="Run ADE API tests (unit by default).")
def test(
    suite: str | None = typer.Argument(
        None,
        help="Suite to run: unit, integration, or all (default: unit).",
    ),
) -> None:
    run_tests(parse_test_suite(suite))


@app.command(name="lint", help="Run ruff and mypy on ade-api.")
def lint(
    fix: bool = typer.Option(False, "--fix", help="Auto-apply lint fixes where supported."),
) -> None:
    run_lint(fix=fix)


@app.command(name="routes", help="List FastAPI routes.")
def routes() -> None:
    run_routes()


@app.command(name="types", help=run_types.__doc__)
def types_() -> None:
    run_types()


__all__ = ["app", "run_dev", "run_start", "run_tests", "run_lint", "run_routes", "run_types"]
