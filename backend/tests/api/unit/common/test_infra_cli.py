from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ade_cli import infra
from ade_cli.local_dev import LocalEnvResult, LocalProfile

runner = CliRunner()


def _local_env_result(*, wrote_file: bool = False) -> LocalEnvResult:
    profile = LocalProfile(
        profile_id="abcd1234",
        project_name="ade-abcd1234",
        db_port=15432,
        blob_port=20000,
        web_port=30000,
        api_port=31000,
    )
    return LocalEnvResult(
        profile=profile,
        values={
            "COMPOSE_PROJECT_NAME": profile.project_name,
            "ADE_LOCAL_DB_PORT": str(profile.db_port),
            "ADE_LOCAL_BLOB_PORT": str(profile.blob_port),
            "ADE_WEB_PORT": str(profile.web_port),
            "ADE_API_PORT": str(profile.api_port),
        },
        path=Path("/tmp/.env"),
        wrote_file=wrote_file,
    )


def test_infra_up_matches_compose_up_defaults(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(infra, "_docker_preflight", lambda: None)
    monkeypatch.setattr(
        infra,
        "ensure_local_env",
        lambda *, force=False: _local_env_result(wrote_file=force),
    )
    monkeypatch.setattr(
        infra,
        "run",
        lambda command, *, cwd=None, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    result = runner.invoke(infra.app, ["up"])

    assert result.exit_code == 0
    assert captured["cwd"] == infra.REPO_ROOT
    assert captured["command"][:2] == ["docker", "compose"]
    assert "up" in captured["command"]
    assert "-d" not in captured["command"]
    assert "--wait" not in captured["command"]


def test_infra_up_force_forwards_passthrough_args(monkeypatch):
    captured: dict[str, object] = {"force": None}

    monkeypatch.setattr(infra, "_docker_preflight", lambda: None)
    monkeypatch.setattr(
        infra,
        "ensure_local_env",
        lambda *, force=False: captured.update({"force": force}) or _local_env_result(),
    )
    monkeypatch.setattr(
        infra,
        "run",
        lambda command, *, cwd=None, env=None: captured.update(
            {"command": list(command), "cwd": cwd}
        ),
    )

    result = runner.invoke(infra.app, ["up", "--force", "-d", "--wait"])

    assert result.exit_code == 0
    assert captured["force"] is True
    assert "-d" in captured["command"]
    assert "--wait" in captured["command"]


def test_infra_down_forwards_compose_options(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(infra, "_docker_preflight", lambda: None)
    monkeypatch.setattr(infra, "ensure_local_env", lambda *, force=False: _local_env_result())
    monkeypatch.setattr(
        infra,
        "run",
        lambda command, *, cwd=None, env=None: captured.update(
            {"command": list(command)}
        ),
    )

    result = runner.invoke(infra.app, ["down", "-v", "--rmi", "all"])

    assert result.exit_code == 0
    assert captured["command"][-4:] == ["down", "-v", "--rmi", "all"]
