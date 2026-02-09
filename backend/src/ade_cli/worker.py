"""`ade-worker` command implementations."""

from __future__ import annotations

import os
import sys

import typer

from ade_worker.gc import run_gc
from ade_worker.worker import main as worker_main
from paths import BACKEND_ROOT

from .common import TestSuite, parse_test_suite, run

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE worker CLI (start, dev, test, gc).",
)
WORKER_TEST_DIR = "tests/worker"
INTEGRATION_TEST_REQUIRED_ENV = ("ADE_TEST_DATABASE_URL",)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="start", help="Start the ADE worker process.")
def start() -> None:
    worker_main()


@app.command(name="dev", help="Run the worker in dev mode (same as start).")
def dev() -> None:
    worker_main()


@app.command(name="test", help="Run ADE worker tests (unit by default).")
def test(
    suite: str | None = typer.Argument(
        None,
        help="Suite to run: unit, integration, or all (default: unit).",
    ),
) -> None:
    resolved = parse_test_suite(suite)
    if not (BACKEND_ROOT / WORKER_TEST_DIR).is_dir():
        typer.echo(
            "error: worker tests require the backend checkout (tests/worker).",
            err=True,
        )
        raise typer.Exit(code=1)

    cmd = [sys.executable, "-m", "pytest", WORKER_TEST_DIR]
    if resolved is not TestSuite.ALL:
        cmd.extend(["-m", resolved.value])
    if resolved is TestSuite.UNIT:
        cmd.extend(["--ignore", f"{WORKER_TEST_DIR}/integration"])
    if resolved is TestSuite.UNIT:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("ADE_")
        }
    else:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("ADE_") or key.startswith("ADE_TEST_")
        }
        missing = [name for name in INTEGRATION_TEST_REQUIRED_ENV if not env.get(name)]
        if missing:
            missing_csv = ", ".join(missing)
            typer.echo(
                "error: integration tests require explicit test environment variables: "
                f"{missing_csv}",
                err=True,
            )
            typer.echo(
                "hint: set ADE_TEST_DATABASE_URL before running worker integration tests.",
                err=True,
            )
            raise typer.Exit(code=1)
    run(cmd, cwd=BACKEND_ROOT, env=env)


@app.command(name="gc", help="Run garbage collection once.")
def gc() -> None:
    run_gc()


__all__ = ["app"]
