"""Test command for ADE API."""

from __future__ import annotations

import sys
from enum import Enum

import typer

from ade_api.commands import common


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


def run_tests(suite: TestSuite) -> None:
    api_root = common.REPO_ROOT / "backend" / "ade-api"
    cmd = [sys.executable, "-m", "pytest"]
    if suite is not TestSuite.ALL:
        cmd.extend(["-m", suite.value])
    if suite is TestSuite.UNIT:
        cmd.extend(["--ignore", "tests/integration"])
    common.run(cmd, cwd=api_root)


def register(app: typer.Typer) -> None:
    @app.command(name="test", help="Run ADE API tests (unit by default).")
    def test(
        suite: str | None = typer.Argument(
            None,
            help="Suite to run: unit, integration, or all (default: unit).",
        ),
    ) -> None:
        run_tests(parse_suite(suite))
