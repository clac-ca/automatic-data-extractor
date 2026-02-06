"""`ade-worker` command implementations."""

from __future__ import annotations

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
    run(cmd, cwd=BACKEND_ROOT)


@app.command(name="gc", help="Run garbage collection once.")
def gc() -> None:
    run_gc()


__all__ = ["app"]

