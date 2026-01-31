"""ade-worker: CLI for ADE worker."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from pathlib import Path

import typer

from .gc import run_gc
from .worker import main as worker_main

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE worker CLI (start, gc, test).",
)

class TestSuite(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    ALL = "all"


def parse_suite(value: str | None) -> TestSuite:
    if value is None:
        return TestSuite.UNIT
    normalized = value.strip().lower()
    if normalized in {"unit", "u"}:
        return TestSuite.UNIT
    if normalized in {"integration", "int", "i"}:
        return TestSuite.INTEGRATION
    if normalized in {"all", "a"}:
        return TestSuite.ALL
    typer.echo("❌ Unknown test suite. Use unit, integration, or all.", err=True)
    raise typer.Exit(code=1)


def _find_repo_root() -> Path:
    def _is_repo_root(path: Path) -> bool:
        return (path / "apps" / "ade-worker" / "pyproject.toml").is_file()

    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if _is_repo_root(candidate):
            return candidate

    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if _is_repo_root(candidate):
            return candidate

    return cwd


def _worker_root() -> Path:
    root = _find_repo_root()
    candidate = root / "apps" / "ade-worker"
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return root


def _run(command: list[str], *, cwd: Path) -> None:
    typer.echo(f"↪️  {' '.join(command)}", err=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def run_tests(suite: TestSuite) -> None:
    worker_root = _worker_root()
    if not (worker_root / "pyproject.toml").is_file():
        typer.echo("❌ Worker tests require the repo checkout (apps/ade-worker).", err=True)
        raise typer.Exit(code=1)

    cmd = [sys.executable, "-m", "pytest"]
    if suite is not TestSuite.ALL:
        cmd.extend(["-m", suite.value])
    if suite is TestSuite.UNIT:
        cmd.extend(["--ignore", "tests/integration"])
    _run(cmd, cwd=worker_root)


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


@app.command(name="gc", help="Run garbage collection once.")
def gc() -> None:
    run_gc()


@app.command(name="test", help="Run ADE worker tests (unit by default).")
def test(
    suite: str | None = typer.Argument(
        None,
        help="Suite to run: unit, integration, or all (default: unit).",
    ),
) -> None:
    run_tests(parse_suite(suite))


if __name__ == "__main__":
    app()
