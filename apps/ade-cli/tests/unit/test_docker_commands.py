from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ade_cli import cli
from ade_cli.commands import common


runner = CliRunner()


def test_docker_passthrough(monkeypatch):
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd=None, env=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "REPO_ROOT", Path("/repo"))
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "docker-bin")
    monkeypatch.setattr(common, "run", fake_run)

    result = runner.invoke(cli.app, ["docker", "ps"])
    assert result.exit_code == 0

    assert recorded["cmd"] == ["docker-bin", "ps"]
    assert recorded["cwd"] == Path("/repo")
