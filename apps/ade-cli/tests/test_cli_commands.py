from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from ade_tools import cli
from ade_tools.commands import build
from ade_tools.commands import ci
from ade_tools.commands import common

runner = CliRunner()


def test_help_includes_documented_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in ("routes", "openapi-types", "ci", "bundle"):
        assert command in result.stdout


def test_ci_continues_when_types_exits_zero(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(ci.common, "refresh_paths", lambda: calls.append("refresh"))

    def fake_types() -> None:
        calls.append("types")
        raise typer.Exit(code=0)

    monkeypatch.setattr(ci, "run_types", fake_types)
    monkeypatch.setattr(ci, "run_lint", lambda scope="all": calls.append(("lint", scope)))
    monkeypatch.setattr(ci, "run_tests", lambda **kwargs: calls.append("tests"))
    monkeypatch.setattr(ci, "run_build", lambda: calls.append("build"))

    ci.run_ci()

    assert calls == ["refresh", "types", ("lint", "all"), "tests", "build"]


def test_build_handles_missing_dist(monkeypatch, tmp_path) -> None:
    frontend = tmp_path / "apps" / "ade-web"
    backend = tmp_path / "apps" / "ade-api" / "src" / "ade_api"
    frontend.mkdir(parents=True)
    backend.mkdir(parents=True)
    (frontend / "package.json").write_text("{}")
    (frontend / "node_modules").mkdir()

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(common, "BACKEND_SRC", backend)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(common, "npm_path", lambda: "npm-bin")
    monkeypatch.setattr(common, "ensure_node_modules", lambda *args, **kwargs: None)
    monkeypatch.setattr(common, "run", lambda *args, **kwargs: None)

    with pytest.raises(typer.Exit):
        build.run_build()
