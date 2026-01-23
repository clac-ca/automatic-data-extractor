from __future__ import annotations

import json
import tomllib
from importlib import metadata
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ade_cli import cli
from ade_cli.commands import build
from ade_cli.commands import ci
from ade_cli.commands import common

runner = CliRunner()


def test_help_includes_documented_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in ("routes", "openapi-types", "ci", "bundle"):
        assert command in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(cli.app, [])
    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "Commands" in result.stdout


def test_version_flag_outputs_version() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    expected_cli_version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    repo_root = Path(__file__).resolve().parents[4]
    expected_api_version = tomllib.loads(
        (repo_root / "apps" / "ade-api" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    try:
        expected_engine_version = metadata.version("ade-engine")
    except metadata.PackageNotFoundError:
        expected_engine_version = None
    expected_worker_version = tomllib.loads(
        (repo_root / "apps" / "ade-worker" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    expected_web_version = json.loads((repo_root / "apps" / "ade-web" / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]

    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    parsed = {}
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        name, version = stripped.split(maxsplit=1)
        parsed[name] = version

    assert parsed["ade-cli"] == expected_cli_version
    assert parsed["ade-api"] == expected_api_version
    if expected_engine_version is not None:
        assert parsed["ade-engine"] == expected_engine_version
    else:
        assert "ade-engine" not in parsed
    assert parsed["ade-worker"] == expected_worker_version
    assert parsed["ade-web"] == expected_web_version


def test_ci_continues_when_types_exits_zero(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(ci.common, "refresh_paths", lambda: calls.append("refresh"))

    def fake_types() -> None:
        calls.append("types")
        raise typer.Exit(code=0)

    monkeypatch.setattr(ci, "run_types", fake_types)
    monkeypatch.setattr(ci, "run_lint", lambda scope="all", fix=False: calls.append(("lint", scope, fix)))
    monkeypatch.setattr(ci, "run_tests", lambda **kwargs: calls.append("tests"))
    monkeypatch.setattr(ci, "run_build", lambda: calls.append("build"))

    ci.run_ci()

    assert calls == ["refresh", "types", ("lint", "all", False), "tests", "build"]


def test_build_handles_missing_dist(monkeypatch, tmp_path) -> None:
    frontend = tmp_path / "apps" / "ade-web"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text("{}")
    (frontend / "node_modules").mkdir()

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(common, "npm_path", lambda: "npm-bin")
    monkeypatch.setattr(common, "ensure_node_modules", lambda *args, **kwargs: None)
    monkeypatch.setattr(common, "run", lambda *args, **kwargs: None)

    with pytest.raises(typer.Exit):
        build.run_build()
