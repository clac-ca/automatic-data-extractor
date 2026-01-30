"""Run test suites across ADE apps."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

import typer

from ade_cli.commands import common


class TestSuite(str, Enum):
    """Supported test suite selections."""

    UNIT = "unit"
    INTEGRATION = "integration"
    ALL = "all"


class TestTarget(str, Enum):
    """Supported test targets."""

    API = "api"
    WORKER = "worker"
    CLI = "cli"
    WEB = "web"
    ALL = "all"


SUITE_ALIASES: dict[str, TestSuite] = {
    "unit": TestSuite.UNIT,
    "u": TestSuite.UNIT,
    "integration": TestSuite.INTEGRATION,
    "int": TestSuite.INTEGRATION,
    "i": TestSuite.INTEGRATION,
    "all": TestSuite.ALL,
    "a": TestSuite.ALL,
}

TARGET_ALIASES: dict[str, TestTarget] = {
    "api": TestTarget.API,
    "backend": TestTarget.API,
    "worker": TestTarget.WORKER,
    "cli": TestTarget.CLI,
    "web": TestTarget.WEB,
    "frontend": TestTarget.WEB,
    "all": TestTarget.ALL,
}


@dataclass(frozen=True)
class TestPlan:
    """Resolved selection for test execution."""

    suite: TestSuite
    targets: list[TestTarget]

    @classmethod
    def from_cli(
        cls,
        suite: str | None,
        targets: Sequence[str] | None,
        *,
        default_suite: TestSuite = TestSuite.UNIT,
    ) -> "TestPlan":
        raw_targets = list(targets or [])
        resolved_suite = _normalize_suite(suite)

        if suite is not None and resolved_suite is None:
            raw_targets.insert(0, suite)
            suite = None

        suite_value = parse_suite(suite, default=default_suite)
        targets_value = parse_targets(raw_targets)
        return cls(suite=suite_value, targets=targets_value)


def _normalize_suite(value: str | None) -> TestSuite | None:
    if value is None:
        return None
    key = value.strip().lower()
    if not key:
        return None
    return SUITE_ALIASES.get(key)


def parse_suite(value: str | None, *, default: TestSuite = TestSuite.UNIT) -> TestSuite:
    """Parse a suite value or return the default."""

    if value is None:
        return default
    resolved = _normalize_suite(value)
    if resolved is None:
        typer.echo(
            f"❌ Unknown test suite '{value}'. Use unit, integration, or all.",
            err=True,
        )
        raise typer.Exit(code=1)
    return resolved


def parse_targets(values: Sequence[str] | None) -> list[TestTarget]:
    """Parse target identifiers into TestTarget list."""

    if not values:
        return [target for target in TestTarget if target is not TestTarget.ALL]

    resolved: list[TestTarget] = []
    for raw in values:
        key = str(raw).strip().lower()
        if not key:
            continue
        target = TARGET_ALIASES.get(key)
        if target is None:
            typer.echo(
                "❌ Unknown test target '{value}'. Use api, worker, cli, web, or all.".format(
                    value=raw
                ),
                err=True,
            )
            raise typer.Exit(code=1)
        if target is TestTarget.ALL:
            return [t for t in TestTarget if t is not TestTarget.ALL]
        if target not in resolved:
            resolved.append(target)

    if not resolved:
        typer.echo("⚠️ No valid test targets selected.", err=True)
        raise typer.Exit(code=1)

    return resolved


def _pytest_command(suite: TestSuite) -> list[str]:
    cmd = [sys.executable, "-m", "pytest"]
    if suite is not TestSuite.ALL:
        cmd.extend(["-m", suite.value])
    return cmd


def _run_python_suite(
    *,
    name: str,
    src_path: Path,
    cwd: Path,
    suite: TestSuite,
) -> bool:
    if not src_path.exists():
        typer.echo(f"⚠️ {name} source directory not found; skipping.", err=True)
        return False

    typer.echo(f"🧪 Running {name} {suite.value} tests (pytest)…")
    common.run(_pytest_command(suite), cwd=cwd)
    return True


def _run_api_suite(suite: TestSuite) -> bool:
    return _run_python_suite(
        name="ade-api",
        src_path=common.BACKEND_SRC,
        cwd=common.BACKEND_DIR,
        suite=suite,
    )


def _run_worker_suite(suite: TestSuite) -> bool:
    worker_dir = common.REPO_ROOT / "apps" / "ade-worker"
    worker_src = worker_dir / "src" / "ade_worker"
    return _run_python_suite(
        name="ade-worker",
        src_path=worker_src,
        cwd=worker_dir,
        suite=suite,
    )


def _run_cli_suite(suite: TestSuite) -> bool:
    return _run_python_suite(
        name="ade-cli",
        src_path=common.CLI_SRC,
        cwd=common.CLI_DIR,
        suite=suite,
    )


def _run_web_suite(suite: TestSuite) -> bool:
    if not common.FRONTEND_DIR.exists():
        typer.echo("⚠️ Web directory not found; skipping web tests.", err=True)
        return False

    pkg = common.load_frontend_package_json()
    if "test" not in pkg.get("scripts", {}):
        typer.echo("⚠️ No 'test' script found in web package.json; skipping web tests.", err=True)
        return False

    if suite is TestSuite.INTEGRATION:
        typer.echo("ℹ️  Web tests do not distinguish suites; running npm test.")

    npm_bin = common.npm_path()
    common.ensure_node_modules()
    typer.echo("🧪 Running ade-web tests (npm run test)…")
    common.run([npm_bin, "run", "test"], cwd=common.FRONTEND_DIR)
    return True


def run_tests(
    *,
    suite: TestSuite = TestSuite.UNIT,
    targets: Sequence[TestTarget] | None = None,
) -> None:
    """Run test suites for the selected targets."""

    common.refresh_paths()

    resolved_targets = list(targets) if targets else parse_targets([])

    python_targets = {
        TestTarget.API,
        TestTarget.WORKER,
        TestTarget.CLI,
    }
    if any(target in python_targets for target in resolved_targets):
        common.require_python_module(
            "pytest",
            "Install API/test dependencies (run `./setup.sh`).",
        )

    ran_any = False

    for target in resolved_targets:
        if target is TestTarget.API:
            ran_any = _run_api_suite(suite) or ran_any
        elif target is TestTarget.WORKER:
            ran_any = _run_worker_suite(suite) or ran_any
        elif target is TestTarget.CLI:
            ran_any = _run_cli_suite(suite) or ran_any
        elif target is TestTarget.WEB:
            ran_any = _run_web_suite(suite) or ran_any

    if not ran_any:
        typer.echo("⚠️ No tests were run (nothing to test).", err=True)
        raise typer.Exit(code=1)

    typer.echo("✅ Tests complete")


def register_target(app: typer.Typer, target: TestTarget) -> None:
    def _register(name: str, *, hidden: bool = False) -> None:
        @app.command(name=name, hidden=hidden, help="Run tests for this app.")
        def test(
            suite: str | None = typer.Argument(
                None,
                help="Suite to run: unit, integration, or all (default: unit).",
            ),
        ) -> None:
            resolved_suite = parse_suite(suite, default=TestSuite.UNIT)
            run_tests(suite=resolved_suite, targets=[target])

    _register("test")


def register(app: typer.Typer) -> None:
    @app.command(
        name="test",
        help=(
            "Run tests. Usage: ade test [suite] [targets...] (suite: unit|integration|all; "
            "targets: api|worker|cli|web|all)."
        ),
    )
    def tests(
        suite: str | None = typer.Argument(
            None,
            help="Suite to run: unit, integration, or all (default: unit).",
        ),
        targets: list[str] = typer.Argument(
            None,
            help="Targets to run: api, worker, cli, web, or all.",
        ),
    ) -> None:
        plan = TestPlan.from_cli(suite, targets, default_suite=TestSuite.UNIT)
        run_tests(suite=plan.suite, targets=plan.targets)
