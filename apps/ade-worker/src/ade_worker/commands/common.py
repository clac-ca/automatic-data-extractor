"""Shared helpers for ADE worker CLI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

import typer


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run(command: Iterable[str], *, cwd: Path | None = None) -> None:
    cmd_list = list(command)
    typer.echo(f"↪️  {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(cmd_list, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def require_command(command: str, *, friendly_name: str | None = None, fix_hint: str | None = None) -> str:
    friendly = friendly_name or command
    found = shutil.which(command)
    if found:
        return found
    hint = fix_hint or "Ensure the command is installed and available on PATH."
    typer.echo(f"❌ {friendly} not found (looked for `{command}`).\n{hint}", err=True)
    raise typer.Exit(code=1)
