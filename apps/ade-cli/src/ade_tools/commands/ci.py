"""CI pipeline command."""

from __future__ import annotations

import typer

from ade_tools.commands import common
from ade_tools.commands.build import run_build
from ade_tools.commands.lint_cmd import run_lint
from ade_tools.commands.tests import run_tests
from ade_tools.commands.types_cmd import run_types


def run_ci(skip_types: bool = False, skip_tests: bool = False) -> None:
    """Run an end-to-end pipeline: openapi-types → lint → test → build."""

    common.refresh_paths()

    if skip_types:
        typer.echo("ℹ️  Skipping OpenAPI type generation (--skip-types).")
    else:
        typer.echo("🧬 Generating OpenAPI types…")
        run_types()

    typer.echo("🔍 Running linters…")
    run_lint(scope="all")

    if skip_tests:
        typer.echo("ℹ️  Skipping tests (--skip-tests).")
    else:
        typer.echo("🧪 Running tests…")
        run_tests()

    typer.echo("🏗️ Building production assets…")
    run_build()
    typer.echo("✅ ci complete")


def register(app: typer.Typer) -> None:
    @app.command(
        name="ci",
        help="Run openapi-types, lint, test, then build (mirrors CI pipeline).",
    )
    def ci(
        skip_types: bool = typer.Option(
            False,
            "--skip-types",
            help="Skip OpenAPI generation/TS types.",
        ),
        skip_tests: bool = typer.Option(
            False,
            "--skip-tests",
            help="Skip backend/frontend tests.",
        ),
    ) -> None:
        run_ci(skip_types=skip_types, skip_tests=skip_tests)
