"""`ade test` command."""

from __future__ import annotations

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="test", help="Run API, worker, and web tests.")
    def test() -> None:
        shared._run(["ade-api", "test"], cwd=shared.REPO_ROOT)
        shared._run(["ade-worker", "test"], cwd=shared.REPO_ROOT)
        shared._run(shared._npm_cmd("run", "test"), cwd=shared.REPO_ROOT)
