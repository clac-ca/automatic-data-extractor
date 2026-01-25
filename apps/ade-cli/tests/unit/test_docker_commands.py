from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ade_cli import cli
from ade_cli.commands import common


runner = CliRunner()


def _setup_docker(monkeypatch, repo_root: Path) -> dict[str, object]:
    recorded: dict[str, object] = {}

    def fake_run(cmd, cwd=None, env=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd

    monkeypatch.delenv("ADE_IMAGE", raising=False)
    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "REPO_ROOT", repo_root)
    monkeypatch.setattr(common, "require_command", lambda *_, **__: "docker-bin")
    monkeypatch.setattr(common, "run", fake_run)
    return recorded


def test_docker_passthrough(monkeypatch):
    recorded = _setup_docker(monkeypatch, Path("/repo"))

    result = runner.invoke(cli.app, ["docker", "ps"])
    assert result.exit_code == 0

    assert recorded["cmd"] == ["docker-bin", "ps"]
    assert recorded["cwd"] == Path("/repo")


def test_docker_build_image_shortcut(monkeypatch, tmp_path):
    recorded = _setup_docker(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["docker", "build"])
    assert result.exit_code == 0

    assert recorded["cmd"] == ["docker-bin", "build", "-t", "ade-app:local", "."]
    assert recorded["cwd"] == tmp_path


def test_docker_run_image_shortcut(monkeypatch, tmp_path):
    recorded = _setup_docker(monkeypatch, tmp_path)

    env_file = tmp_path / ".env"
    env_file.write_text("ADE_API_PORT=9001\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    result = runner.invoke(cli.app, ["docker", "run"])
    assert result.exit_code == 0

    assert recorded["cmd"] == [
        "docker-bin",
        "run",
        "--rm",
        "-it",
        "--env-file",
        str(env_file),
        "-e",
        "ADE_DATA_DIR=/app/data",
        "-p",
        "9001:9001",
        "-v",
        f"{data_dir}:/app/data",
        "ade-app:local",
    ]
    assert recorded["cwd"] == tmp_path


def test_docker_run_worker_shortcut(monkeypatch, tmp_path):
    recorded = _setup_docker(monkeypatch, tmp_path)

    env_file = tmp_path / ".env"
    env_file.write_text("ADE_API_PORT=9001\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    result = runner.invoke(cli.app, ["docker", "worker"])
    assert result.exit_code == 0

    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert "docker-bin" in cmd[0]
    assert "-p" not in cmd
    assert cmd[-3:] == ["ade-app:local", "worker", "start"]


def test_docker_passthrough_explicit(monkeypatch, tmp_path):
    recorded = _setup_docker(monkeypatch, tmp_path)

    result = runner.invoke(cli.app, ["docker", "--", "ps"])
    assert result.exit_code == 0

    assert recorded["cmd"] == ["docker-bin", "ps"]
    assert recorded["cwd"] == tmp_path
