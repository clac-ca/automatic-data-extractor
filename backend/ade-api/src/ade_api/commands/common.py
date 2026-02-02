"""Shared helpers for ADE API CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import typer


def _find_repo_root() -> Path:
    def _is_repo_root(path: Path) -> bool:
        return (path / "backend" / "pyproject.toml").is_file()

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
FRONTEND_DIR = REPO_ROOT / "frontend" / "ade-web"


def run(
    command: Iterable[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd_list = list(command)
    typer.echo(f"↪️  {' '.join(cmd_list)}", err=True)
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
    typer.echo(f"❌ {friendly} not found (looked for `{command}`).\n{hint}", err=True)
    raise typer.Exit(code=1)


def uvicorn_path() -> str:
    candidate = Path(shutil.which("uvicorn") or "")
    if candidate.exists():
        return str(candidate)
    return require_command(
        "uvicorn",
        friendly_name="uvicorn",
        fix_hint="Install ADE API dependencies (run `./setup.sh`).",
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
        typer.echo("⚠️  frontend directory missing; expected frontend/ade-web", err=True)
        raise typer.Exit(code=1)
    if not (directory / "package.json").exists():
        typer.echo("⚠️  package.json missing in frontend/ade-web; cannot continue.", err=True)
        raise typer.Exit(code=1)
    if not (directory / "node_modules").exists():
        typer.echo(
            "❌ Frontend dependencies not installed. Run `npm install` in frontend/ade-web.",
            err=True,
        )
        raise typer.Exit(code=1)


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return value[:idx].rstrip()
    return value


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    dotenv_path = path or (REPO_ROOT / ".env")
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_inline_comment(raw_value.strip())
        value = _unquote(value.strip())
        if value == "":
            continue
        values.setdefault(key, value)
    return values


def build_env(dotenv_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key, value in load_dotenv(dotenv_path).items():
        env.setdefault(key, value)
    return env
