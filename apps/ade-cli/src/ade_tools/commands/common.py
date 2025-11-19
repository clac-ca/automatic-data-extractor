"""Shared helpers and filesystem paths for the ADE CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

import typer


def _find_repo_root() -> Path:
    """Best-effort detection of the ADE repo root."""

    def _is_repo_root(path: Path) -> bool:
        return (path / "apps" / "ade-api" / "pyproject.toml").is_file()

    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if _is_repo_root(candidate):
            return candidate

    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if _is_repo_root(candidate):
            return candidate

    return cwd


REPO_ROOT = _find_repo_root()
BACKEND_DIR = REPO_ROOT / "apps" / "ade-api"
BACKEND_SRC = BACKEND_DIR / "src" / "ade_api"
FRONTEND_DIR = REPO_ROOT / "apps" / "ade-web"
VENV_DIR = REPO_ROOT / ".venv"
COMPOSE_FILE = REPO_ROOT / "infra" / "compose.yaml"
README_HINT = "See README: Developer Setup."


def refresh_paths() -> None:
    """Refresh global path constants based on the current working directory."""

    global REPO_ROOT, BACKEND_DIR, BACKEND_SRC, FRONTEND_DIR, VENV_DIR, COMPOSE_FILE
    REPO_ROOT = _find_repo_root()
    BACKEND_DIR = REPO_ROOT / "apps" / "ade-api"
    BACKEND_SRC = BACKEND_DIR / "src" / "ade_api"
    FRONTEND_DIR = REPO_ROOT / "apps" / "ade-web"
    VENV_DIR = REPO_ROOT / ".venv"
    COMPOSE_FILE = REPO_ROOT / "infra" / "compose.yaml"


def run(command: Iterable[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run a command, streaming output and raising on failure."""

    cmd_list = list(command)
    typer.echo(f"↪️  {' '.join(cmd_list)}", err=True)
    completed = subprocess.run(
        cmd_list,
        cwd=cwd,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def ensure_frontend_dir() -> None:
    if not FRONTEND_DIR.exists():
        typer.echo("⚠️  frontend directory missing; expected apps/ade-web", err=True)
        raise typer.Exit(code=1)


def ensure_backend_dir() -> None:
    if not BACKEND_SRC.exists():
        typer.echo("⚠️  backend directory missing; expected apps/ade-api/src/ade_api", err=True)
        raise typer.Exit(code=1)


def ensure_compose_file() -> None:
    """Ensure the Docker compose file exists in the expected location."""

    if not COMPOSE_FILE.exists():
        typer.echo(f"⚠️  docker compose file missing; expected {COMPOSE_FILE}", err=True)
        raise typer.Exit(code=1)


def require_command(command: str, friendly_name: Optional[str] = None, fix_hint: Optional[str] = None) -> str:
    """Ensure a binary exists on PATH and return its resolved path."""

    friendly = friendly_name or command
    found = shutil.which(command)
    if found:
        return found

    hint = f"{fix_hint}\n\n{README_HINT}" if fix_hint else README_HINT
    typer.echo(
        f"❌ {friendly} not found (looked for `{command}`).\n{hint}",
        err=True,
    )
    raise typer.Exit(code=1)


def require_python_module(module: str, fix_hint: str) -> None:
    """Ensure a Python module is importable in the current environment."""

    import importlib.util

    if importlib.util.find_spec(module) is None:
        typer.echo(
            f"❌ Required Python module '{module}' is unavailable in the current environment.\n{fix_hint}\n\n{README_HINT}",
            err=True,
        )
        raise typer.Exit(code=1)


def ensure_node_modules(frontend_dir: Path | None = None) -> None:
    """Fail fast when frontend dependencies have not been installed."""

    directory = frontend_dir or FRONTEND_DIR
    if not directory.exists():
        typer.echo("⚠️  frontend directory missing; expected apps/ade-web", err=True)
        raise typer.Exit(code=1)
    if not (directory / "package.json").exists():
        typer.echo("⚠️  package.json missing in apps/ade-web; cannot continue.", err=True)
        raise typer.Exit(code=1)
    if not (directory / "node_modules").exists():
        typer.echo("❌ Frontend dependencies not installed. Run `npm install` in apps/ade-web.", err=True)
        raise typer.Exit(code=1)


def uvicorn_path() -> str:
    """Return the uvicorn executable in the current environment."""

    return require_command(
        "uvicorn",
        friendly_name="uvicorn",
        fix_hint="Install ADE into an active virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )


def npm_path() -> str:
    """Return the npm executable in the current environment."""

    return require_command(
        "npm",
        friendly_name="npm",
        fix_hint="Install Node.js (LTS) and ensure `npm` is on your PATH.",
    )


def run_parallel(tasks: list[tuple[str, list[str], Path | None, dict[str, str]]]) -> None:
    """Run multiple long-lived commands in parallel until one exits."""

    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    try:
        for name, cmd, cwd, env in tasks:
            typer.echo(f"▶️  starting {name}: {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env or os.environ.copy(),
            )
            processes.append((name, proc))

        while processes:
            time.sleep(0.25)
            for name, proc in list(processes):
                code = proc.poll()
                if code is None:
                    continue
                if code != 0:
                    typer.echo(f"❌ {name} exited with code {code}", err=True)
                    raise typer.Exit(code=code)
                typer.echo(f"✅ {name} exited")
                processes.remove((name, proc))
    except KeyboardInterrupt:
        typer.echo("\n🛑 received interrupt; stopping child processes...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                typer.echo(f"⏹️  terminating {name}")
                proc.terminate()
        for _, proc in processes:
            if proc.poll() is None:
                proc.wait(timeout=5)


def load_frontend_package_json() -> dict:
    pkg_path = FRONTEND_DIR / "package.json"
    if not pkg_path.exists():
        return {}
    return json.loads(pkg_path.read_text(encoding="utf-8"))
