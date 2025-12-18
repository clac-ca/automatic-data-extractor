from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ade_cli import cli
from ade_cli.commands import common


runner = CliRunner()


def test_docker_compose_injects_compose_file(monkeypatch, tmp_path):
    compose = tmp_path / "compose.yaml"
    compose.parent.mkdir(parents=True, exist_ok=True)
    compose.write_text("services: {}")

    calls: dict[str, object] = {}
    monkeypatch.setattr(common, "refresh_paths", lambda: calls.setdefault("refreshed", True))
    monkeypatch.setattr(common, "ensure_compose_file", lambda: calls.setdefault("ensured_compose", True))
    monkeypatch.setattr(common, "COMPOSE_FILE", compose)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "/usr/bin/docker")
    monkeypatch.setattr(common, "run", lambda cmd, cwd=None, env=None: calls.setdefault("cmd", cmd))

    result = runner.invoke(cli.app, ["docker", "compose", "up", "-d", "--build"])
    assert result.exit_code == 0

    assert calls["refreshed"] is True
    assert calls["ensured_compose"] is True
    assert calls["cmd"][0] == "/usr/bin/docker"
    assert calls["cmd"] == ["/usr/bin/docker", "compose", "-f", str(compose), "up", "-d", "--build"]


def test_docker_compose_respects_user_file(monkeypatch, tmp_path):
    compose = tmp_path / "compose.yaml"
    compose.parent.mkdir(parents=True, exist_ok=True)
    compose.write_text("services: {}")

    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd=None, env=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "ensure_compose_file", lambda: recorded.setdefault("ensured_compose", True))
    monkeypatch.setattr(common, "COMPOSE_FILE", compose)
    monkeypatch.setattr(common, "REPO_ROOT", Path("/repo"))
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "docker-bin")
    monkeypatch.setattr(common, "run", fake_run)

    result = runner.invoke(cli.app, ["docker", "compose", "-f", "other.yaml", "logs", "--tail", "50", "ade"])
    assert result.exit_code == 0

    assert recorded.get("ensured_compose") is None
    assert recorded["cmd"] == ["docker-bin", "compose", "-f", "other.yaml", "logs", "--tail", "50", "ade"]
    assert recorded["cwd"] == Path("/repo")


def test_docker_passthrough_non_compose(monkeypatch):
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd=None, env=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "ensure_compose_file", lambda: recorded.setdefault("ensured_compose", True))
    monkeypatch.setattr(common, "REPO_ROOT", Path("/repo"))
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "docker-bin")
    monkeypatch.setattr(common, "run", fake_run)

    result = runner.invoke(cli.app, ["docker", "ps"])
    assert result.exit_code == 0

    assert recorded.get("ensured_compose") is None
    assert recorded["cmd"] == ["docker-bin", "ps"]
    assert recorded["cwd"] == Path("/repo")
