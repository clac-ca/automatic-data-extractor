"""ade: Python orchestration CLI for ADE."""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path
import tomllib

import typer

from ade_cli.commands import register_project
from ade_cli.commands import web_cmd
from ade_cli.commands import cli_cmd
from ade_api.cli import app as api_app
from ade_worker.cli import app as worker_app

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="ADE orchestration CLI for ADE backend/frontend dev, builds, and local Docker helpers.",
)


def _dist_version(dist_name: str) -> str | None:
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return None


def _pyproject_version(pyproject: Path) -> str | None:
    if not pyproject.exists():
        return None

    try:
        parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    version = parsed.get("project", {}).get("version")
    if isinstance(version, str) and version:
        return version
    return None


def _package_json_version(package_json: Path) -> str | None:
    if not package_json.exists():
        return None

    try:
        parsed = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version = parsed.get("version")
    if isinstance(version, str) and version:
        return version
    return None


def _resolve_versions() -> list[tuple[str, str]]:
    try:
        from ade_cli.commands import common

        common.refresh_paths()
        repo_root = common.REPO_ROOT
    except Exception:
        repo_root = None

    cli_pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    cli_version = _pyproject_version(cli_pyproject) or _dist_version("ade-cli") or "unknown"

    versions: list[tuple[str, str]] = [("ade-cli", cli_version)]

    if repo_root is not None:
        api_pyproject = repo_root / "apps" / "ade-api" / "pyproject.toml"
        worker_pyproject = repo_root / "apps" / "ade-worker" / "pyproject.toml"
        web_package_json = repo_root / "apps" / "ade-web" / "package.json"
    else:
        api_pyproject = None
        worker_pyproject = None
        web_package_json = None

    api_version = (_pyproject_version(api_pyproject) if api_pyproject is not None else None) or _dist_version(
        "ade-api"
    )
    if api_version:
        versions.append(("ade-api", api_version))

    engine_version = _dist_version("ade-engine")
    if engine_version:
        versions.append(("ade-engine", engine_version))

    worker_version = (
        (_pyproject_version(worker_pyproject) if worker_pyproject is not None else None) or _dist_version("ade-worker")
    )
    if worker_version:
        versions.append(("ade-worker", worker_version))

    web_version = _package_json_version(web_package_json) if web_package_json is not None else None
    if web_version:
        versions.append(("ade-web", web_version))

    return versions


def _version_callback(value: bool) -> None:
    if not value:
        return

    payload = "\n".join(f"{name} {version}" for name, version in _resolve_versions())
    typer.echo(payload)
    raise typer.Exit()


@app.callback()
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show component versions and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    if version:
        return

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


register_project(app)
app.add_typer(api_app, name="api")
app.add_typer(worker_app, name="worker")
app.add_typer(web_cmd.app, name="web")
app.add_typer(cli_cmd.app, name="cli")


if __name__ == "__main__":
    app()
