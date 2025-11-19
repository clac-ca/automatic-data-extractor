"""Test command."""

from __future__ import annotations

import sys

import typer

from ade_tools.commands import common


def run_tests(
    backend: bool = True,
    frontend: bool = True,
    backend_only: bool = False,
    frontend_only: bool = False,
) -> None:
    """
    Run backend and/or frontend tests.

    By default runs both backend (pytest) and frontend (npm test, if defined).
    Use --backend-only / --frontend-only to narrow the scope.
    """
    common.refresh_paths()

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

    ran_any = False

    # ------------------ Backend tests ------------------
    if backend:
        if common.BACKEND_SRC.exists():
            typer.echo("🧪 Running backend tests (pytest)…")
            common.require_python_module(
                "pytest",
                "Install backend/test dependencies (e.g., `pip install -e apps/ade-cli -e packages/ade-schemas -e apps/ade-engine -e apps/ade-api`).",
            )
            common.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=common.BACKEND_DIR,
            )
            ran_any = True
        else:
            typer.echo("⚠️ Backend source directory not found; skipping backend tests.", err=True)

    # ------------------ Frontend tests ------------------
    if frontend:
        if common.FRONTEND_DIR.exists():
            npm_bin = common.npm_path()
            pkg = common.load_frontend_package_json()
            if "test" in pkg.get("scripts", {}):
                common.ensure_node_modules()
                typer.echo("🧪 Running frontend tests (npm run test)…")
                common.run([npm_bin, "run", "test"], cwd=common.FRONTEND_DIR)
                ran_any = True
            else:
                typer.echo("⚠️ No 'test' script found in frontend package.json; skipping frontend tests.", err=True)
        else:
            typer.echo("⚠️ Frontend directory not found; skipping frontend tests.", err=True)

    if not ran_any:
        typer.echo("⚠️ No tests were run (nothing to test).")
    else:
        typer.echo("✅ Tests complete")


def register(app: typer.Typer) -> None:
    @app.command(name="test", help="Run backend and/or frontend tests.")
    def test(
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
