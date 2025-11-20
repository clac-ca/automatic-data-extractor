"""Workpackage command (legacy Node helper)."""

from __future__ import annotations

import typer

from ade_tools.commands import common


def run_workpackage(args: list[str]) -> None:
    """Delegate to scripts/npm-workpackage.mjs (passes all args through)."""

    common.refresh_paths()

    script = common.REPO_ROOT / "scripts" / "npm-workpackage.mjs"
    if not script.exists():
        typer.echo("⚠️  workpackage helper missing; expected scripts/npm-workpackage.mjs", err=True)
        raise typer.Exit(code=1)

    node_bin = common.require_command(
        "node",
        friendly_name="node",
        fix_hint="Install Node.js (LTS) to use the workpackage helper.",
    )
    common.run([node_bin, str(script), *args], cwd=common.REPO_ROOT)


def register(app: typer.Typer) -> None:
    @app.command(
        name="workpackage",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        help="Manage .workpackage records via the legacy Node helper (args passed through).",
    )
    def workpackage(ctx: typer.Context) -> None:
        run_workpackage(list(ctx.args))
