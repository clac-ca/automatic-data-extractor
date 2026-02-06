"""`ade reset` command."""

from __future__ import annotations

import shutil
from typing import Annotated

import typer

from .. import shared


def register(app: typer.Typer) -> None:
    @app.command(name="reset", help="Reset DB, storage, and local state (destructive).")
    def reset(
        db: bool = typer.Option(True, "--db/--no-db", help="Reset the database."),
        storage: bool = typer.Option(True, "--storage/--no-storage", help="Reset blob storage."),
        data: bool = typer.Option(True, "--data/--no-data", help="Clear local data directory."),
        venv: bool = typer.Option(True, "--venv/--no-venv", help="Remove local virtualenvs."),
        storage_mode: Annotated[
            shared.StorageResetMode,
            typer.Option(
                "--storage-mode",
                help="Storage reset mode: prefix (default) or container.",
            ),
        ] = shared.StorageResetMode.PREFIX,
        yes: bool = typer.Option(False, "--yes", help="Confirm destructive reset."),
    ) -> None:
        if not yes:
            typer.echo("error: reset requires --yes", err=True)
            raise typer.Exit(code=1)

        if db:
            shared._run(["ade-db", "reset", "--yes"], cwd=shared.REPO_ROOT)
        if storage:
            shared._run(
                ["ade-storage", "reset", "--yes", "--mode", storage_mode.value],
                cwd=shared.REPO_ROOT,
            )
        if data:
            data_dir = shared.BACKEND_ROOT / "data"
            if data_dir.exists():
                shutil.rmtree(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
        if venv:
            shared._remove_dir(shared.BACKEND_ROOT / ".venv")
            shared._remove_dir(shared.REPO_ROOT / ".venv")
