"""Shared helpers for ADE API CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import typer
from dotenv import dotenv_values

from ade_common.paths import FRONTEND_DIR, REPO_ROOT


def run(
    command: Iterable[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd_list = list(command)
    typer.echo(f"-> {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(cmd_list, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def require_command(
    command: str,
    *,
    friendly_name: str | None = None,
    fix_hint: str | None = None,
) -> str:
    friendly = friendly_name or command
    found = shutil.which(command)
    if found:
        return found

    hint = fix_hint or "Ensure the command is installed and available on PATH."
    typer.echo(f"error: {friendly} not found (looked for `{command}`).\n{hint}", err=True)
    raise typer.Exit(code=1)


def uvicorn_path() -> str:
    candidate = Path(shutil.which("uvicorn") or "")
    if candidate.exists():
        return str(candidate)
    return require_command(
        "uvicorn",
        friendly_name="uvicorn",
        fix_hint="Install dependencies from repo root with `./setup.sh`.",
    )


def npm_path() -> str:
    return require_command(
        "npm",
        friendly_name="npm",
        fix_hint="Install Node.js (LTS) and ensure `npm` is on PATH.",
    )


def load_frontend_package_json() -> dict:
    pkg_path = FRONTEND_DIR / "package.json"
    if not pkg_path.exists():
        return {}
    return json.loads(pkg_path.read_text(encoding="utf-8"))


def ensure_node_modules(frontend_dir: Path | None = None) -> None:
    directory = frontend_dir or FRONTEND_DIR
    if not directory.exists():
        typer.echo("warning: frontend directory missing; expected frontend", err=True)
        raise typer.Exit(code=1)
    if not (directory / "package.json").exists():
        typer.echo("warning: package.json missing in frontend; cannot continue.", err=True)
        raise typer.Exit(code=1)
    if not (directory / "node_modules").exists():
        typer.echo(
            "error: frontend dependencies not installed (run `./setup.sh` from repo root).",
            err=True,
        )
        raise typer.Exit(code=1)


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    dotenv_path = path or (REPO_ROOT / ".env")
    if not dotenv_path.exists():
        return {}
    values: dict[str, str] = {}
    for key, value in dotenv_values(dotenv_path).items():
        if not key or value in {None, ""}:
            continue
        values[key] = value
    return values


def build_env(dotenv_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key, value in load_dotenv(dotenv_path).items():
        env.setdefault(key, value)
    return env
