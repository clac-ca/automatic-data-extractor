"""CLI self-test/lint command group."""

from __future__ import annotations

import typer

from ade_cli.commands import lint_cmd
from ade_cli.commands import tests as tests_cmd

app = typer.Typer(
    help="ADE CLI commands (test, lint).",
    invoke_without_command=True,
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command(name="test", help="Run ade-cli tests.")
def test(
    suite: str | None = typer.Argument(
        None,
        help="Suite to run: unit, integration, or all (default: unit).",
    ),
) -> None:
    resolved = tests_cmd.parse_suite(suite, default=tests_cmd.TestSuite.UNIT)
    tests_cmd.run_tests(suite=resolved, targets=[tests_cmd.TestTarget.CLI])


@app.command(name="lint", help="Run ade-cli linting (ruff).")
def lint(
    fix: bool = typer.Option(False, "--fix", help="Auto-apply lint fixes where supported."),
) -> None:
    lint_cmd.run_lint(scope="cli", fix=fix)
