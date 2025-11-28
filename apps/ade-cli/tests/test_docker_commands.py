from __future__ import annotations

from pathlib import Path

from ade_tools.commands import common, docker


def test_docker_up_uses_docker_cli(monkeypatch, tmp_path):
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

    docker.docker_up()

    assert calls["refreshed"] is True
    assert calls["ensured_compose"] is True
    assert calls["cmd"][0] == "/usr/bin/docker"
    assert "-f" in calls["cmd"]
    assert str(compose) in calls["cmd"]


def test_docker_logs_passes_service(monkeypatch, tmp_path):
    compose = tmp_path / "compose.yaml"
    compose.parent.mkdir(parents=True, exist_ok=True)
    compose.write_text("services: {}")

    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd=None, env=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "ensure_compose_file", lambda: None)
    monkeypatch.setattr(common, "COMPOSE_FILE", compose)
    monkeypatch.setattr(common, "REPO_ROOT", Path("/repo"))
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "docker-bin")
    monkeypatch.setattr(common, "run", fake_run)

    docker.docker_logs(service="api", follow=False, tail=50)

    assert recorded["cmd"] == ["docker-bin", "compose", "-f", str(compose), "logs", "--tail", "50", "api"]
    assert recorded["cwd"] == Path("/repo")
