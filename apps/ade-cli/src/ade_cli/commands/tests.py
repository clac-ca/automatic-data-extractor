"""Run backend/frontend test suites."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import typer

from ade_cli.commands import common


@dataclass(frozen=True)
class TestTargets:
    """Resolved selection for which suites to run."""

    backend: bool
    frontend: bool

    @classmethod
    def from_flags(
        cls,
        *,
        backend: bool,
        frontend: bool,
        backend_only: bool,
        frontend_only: bool,
    ) -> "TestTargets":
        if backend_only and frontend_only:
            typer.echo("❌ Cannot use --backend-only and --frontend-only together.", err=True)
            raise typer.Exit(code=1)

        if backend_only:
            backend, frontend = True, False
        elif frontend_only:
            backend, frontend = False, True

        if not backend and not frontend:
            typer.echo("⚠️ Neither backend nor frontend selected; nothing to test.", err=True)
            raise typer.Exit(code=1)

        return cls(backend=backend, frontend=frontend)


def _run_backend_suite() -> bool:
    """Execute python backend tests (api + engine + cli) via pytest."""

    suites: list[tuple[str, str, Path, Path]] = [
        ("ade-api", "apps/ade-api", common.BACKEND_SRC, common.BACKEND_DIR),
        ("ade-engine", "apps/ade-engine", common.ENGINE_SRC, common.ENGINE_DIR),
        ("ade-cli", "apps/ade-cli", common.CLI_SRC, common.CLI_DIR),
    ]

    any_ran = False

    common.require_python_module(
        "pytest",
        "Install backend/test dependencies (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )

    for name, display_path, src_path, cwd in suites:
        if not src_path.exists():
            typer.echo(f"⚠️ {name} source directory not found ({display_path}); skipping.", err=True)
            continue

        typer.echo(f"🧪 Running {name} tests (pytest)…")
        common.run([sys.executable, "-m", "pytest"], cwd=cwd)
        any_ran = True

    return any_ran


def _run_frontend_suite() -> bool:
    """Execute frontend tests via npm if the project exposes a test script."""
    if not common.FRONTEND_DIR.exists():
        typer.echo("⚠️ Frontend directory not found; skipping frontend tests.", err=True)
        return False

    pkg = common.load_frontend_package_json()
    if "test" not in pkg.get("scripts", {}):
        typer.echo("⚠️ No 'test' script found in frontend package.json; skipping frontend tests.", err=True)
        return False

    npm_bin = common.npm_path()
    common.ensure_node_modules()
    typer.echo("🧪 Running frontend tests (npm run test)…")
    common.run([npm_bin, "run", "test"], cwd=common.FRONTEND_DIR)
    return True


def run_tests(
    backend: bool = True,
    frontend: bool = True,
    backend_only: bool = False,
    frontend_only: bool = False,
) -> None:
    """
    Run backend/frontend tests; flags: --backend-only, --frontend-only, --no-backend, --no-frontend.

    By default runs both backend (pytest) and frontend (npm test, if defined).
    Use --backend-only / --frontend-only to narrow the scope.
    """
    common.refresh_paths()
    targets = TestTargets.from_flags(
        backend=backend,
        frontend=frontend,
        backend_only=backend_only,
        frontend_only=frontend_only,
    )

    ran_any = False

    if targets.backend:
        ran_any = _run_backend_suite() or ran_any

    if targets.frontend:
        ran_any = _run_frontend_suite() or ran_any

    if not ran_any:
        typer.echo("⚠️ No tests were run (nothing to test).", err=True)
        raise typer.Exit(code=1)

    typer.echo("✅ Tests complete")


def register(app: typer.Typer) -> None:
    def _register_command(*, name: str, hidden: bool = False) -> None:
        @app.command(
            name=name,
            help="Run backend/frontend tests; flags: --backend-only, --frontend-only, --no-backend, --no-frontend.",
            hidden=hidden,
        )
        def tests(
            backend: bool = typer.Option(
                True,
                "--backend/--no-backend",
                help="Run backend tests (pytest).",
            ),
            frontend: bool = typer.Option(
                True,
                "--frontend/--no-frontend",
                help="Run frontend tests (npm test, if defined).",
            ),
            backend_only: bool = typer.Option(
                False,
                "--backend-only",
                help="Shortcut for backend only (same as --backend --no-frontend).",
            ),
            frontend_only: bool = typer.Option(
                False,
                "--frontend-only",
                help="Shortcut for frontend only (same as --frontend --no-backend).",
            ),
        ) -> None:
            run_tests(
                backend=backend,
                frontend=frontend,
                backend_only=backend_only,
                frontend_only=frontend_only,
            )

    _register_command(name="tests")
    _register_command(name="test", hidden=True)
