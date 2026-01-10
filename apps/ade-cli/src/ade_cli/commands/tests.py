"""Run API/web test suites."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import typer

from ade_cli.commands import common


@dataclass(frozen=True)
class TestTargets:
    """Resolved selection for which suites to run."""

    api: bool
    web: bool

    @classmethod
    def from_flags(
        cls,
        *,
        api: bool,
        web: bool,
        api_only: bool,
        web_only: bool,
    ) -> "TestTargets":
        if api_only and web_only:
            typer.echo("❌ Cannot use --api-only and --web-only together.", err=True)
            raise typer.Exit(code=1)

        if api_only:
            api, web = True, False
        elif web_only:
            api, web = False, True

        if not api and not web:
            typer.echo("⚠️ Neither API nor web selected; nothing to test.", err=True)
            raise typer.Exit(code=1)

        return cls(api=api, web=web)


def _run_api_suite() -> bool:
    """Execute python API tests (api + engine + cli + worker) via pytest."""

    worker_dir = common.REPO_ROOT / "apps" / "ade-worker"
    worker_src = worker_dir / "src" / "ade_worker"

    suites: list[tuple[str, str, Path, Path]] = [
        ("ade-api", "apps/ade-api", common.BACKEND_SRC, common.BACKEND_DIR),
        ("ade-engine", "apps/ade-engine", common.ENGINE_SRC, common.ENGINE_DIR),
        ("ade-cli", "apps/ade-cli", common.CLI_SRC, common.CLI_DIR),
        ("ade-worker", "apps/ade-worker", worker_src, worker_dir),
    ]

    any_ran = False

    common.require_python_module(
        "pytest",
        "Install API/test dependencies (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )

    for name, display_path, src_path, cwd in suites:
        if not src_path.exists():
            typer.echo(f"⚠️ {name} source directory not found ({display_path}); skipping.", err=True)
            continue

        typer.echo(f"🧪 Running {name} tests (pytest)…")
        common.run([sys.executable, "-m", "pytest"], cwd=cwd)
        any_ran = True

    return any_ran


def _run_web_suite() -> bool:
    """Execute web tests via npm if the project exposes a test script."""
    if not common.FRONTEND_DIR.exists():
        typer.echo("⚠️ Web directory not found; skipping web tests.", err=True)
        return False

    pkg = common.load_frontend_package_json()
    if "test" not in pkg.get("scripts", {}):
        typer.echo("⚠️ No 'test' script found in web package.json; skipping web tests.", err=True)
        return False

    npm_bin = common.npm_path()
    common.ensure_node_modules()
    typer.echo("🧪 Running web tests (npm run test)…")
    common.run([npm_bin, "run", "test"], cwd=common.FRONTEND_DIR)
    return True


def run_tests(
    api: bool = True,
    web: bool = True,
    api_only: bool = False,
    web_only: bool = False,
) -> None:
    """
    Run API/web tests; flags: --api-only, --web-only, --no-api, --no-web.

    By default runs both API (pytest) and web (npm test, if defined).
    Use --api-only / --web-only to narrow the scope.
    """
    common.refresh_paths()
    targets = TestTargets.from_flags(
        api=api,
        web=web,
        api_only=api_only,
        web_only=web_only,
    )

    ran_any = False

    if targets.api:
        ran_any = _run_api_suite() or ran_any

    if targets.web:
        ran_any = _run_web_suite() or ran_any

    if not ran_any:
        typer.echo("⚠️ No tests were run (nothing to test).", err=True)
        raise typer.Exit(code=1)

    typer.echo("✅ Tests complete")


def register(app: typer.Typer) -> None:
    def _register_command(*, name: str, hidden: bool = False) -> None:
        @app.command(
            name=name,
            help="Run API/web tests; flags: --api-only, --web-only, --no-api, --no-web.",
            hidden=hidden,
        )
        def tests(
            api: bool = typer.Option(
                True,
                "--api/--no-api",
                help="Run API tests (pytest).",
            ),
            web: bool = typer.Option(
                True,
                "--web/--no-web",
                help="Run web tests (npm test, if defined).",
            ),
            api_only: bool = typer.Option(
                False,
                "--api-only",
                help="Shortcut for API only (same as --api --no-web).",
            ),
            web_only: bool = typer.Option(
                False,
                "--web-only",
                help="Shortcut for web only (same as --web --no-api).",
            ),
        ) -> None:
            run_tests(
                api=api,
                web=web,
                api_only=api_only,
                web_only=web_only,
            )

    _register_command(name="tests")
    _register_command(name="test", hidden=True)
