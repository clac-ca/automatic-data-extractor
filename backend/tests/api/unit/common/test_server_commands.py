from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from ade_cli import api
from paths import BACKEND_ROOT


def _stub_settings(
    *,
    api_host: str | None = None,
    api_processes: int | None = None,
    api_proxy_headers_enabled: bool = True,
    api_forwarded_allow_ips: str = "127.0.0.1",
    access_log_enabled: bool = True,
):
    return SimpleNamespace(
        api_host=api_host,
        api_processes=api_processes,
        api_proxy_headers_enabled=api_proxy_headers_enabled,
        api_forwarded_allow_ips=api_forwarded_allow_ips,
        effective_api_log_level="INFO",
        access_log_enabled=access_log_enabled,
    )


def test_run_dev_defaults_to_single_process_reload(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(api, "Settings", lambda: _stub_settings(api_processes=9))

    def _fake_run(command, *, cwd, env=None):
        captured["command"] = list(command)
        captured["cwd"] = cwd
        captured["env"] = env

    monkeypatch.setattr(api, "run", _fake_run)

    api.run_dev()

    command = captured["command"]
    assert command[:3] == [api.sys.executable, "-m", "uvicorn"]
    assert "--reload" in command
    assert "--workers" not in command

    reload_dirs = []
    for idx, token in enumerate(command):
        if token == "--reload-dir":
            reload_dirs.append(command[idx + 1])
    assert reload_dirs == list(api.DEV_RELOAD_DIRS)
    assert captured["cwd"] == BACKEND_ROOT
    assert captured["env"]["ADE_API_PROCESSES"] == "1"


def test_run_dev_processes_flag_disables_reload(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(api, "Settings", lambda: _stub_settings(api_processes=1))
    monkeypatch.setattr(
        api,
        "run",
        lambda command, *, cwd, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    api.run_dev(processes=3)

    command = captured["command"]
    assert "--reload" not in command
    assert command[command.index("--workers") + 1] == "3"
    assert captured["env"]["ADE_API_PROCESSES"] == "3"


def test_run_start_uses_uvicorn_production_profile(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        api,
        "Settings",
        lambda: _stub_settings(
            api_processes=2,
            api_proxy_headers_enabled=True,
            api_forwarded_allow_ips="127.0.0.1",
        ),
    )
    monkeypatch.setattr(
        api,
        "run",
        lambda command, *, cwd, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    api.run_start()

    command = captured["command"]
    assert command[:3] == [api.sys.executable, "-m", "uvicorn"]
    assert command[command.index("--loop") + 1] == "uvloop"
    assert command[command.index("--http") + 1] == "httptools"
    assert "--proxy-headers" in command
    assert command[command.index("--forwarded-allow-ips") + 1] == "127.0.0.1"
    assert command[command.index("--workers") + 1] == "2"
    assert "--no-proxy-headers" not in command
    assert captured["env"]["ADE_API_PROCESSES"] == "2"


def test_run_start_supports_disabling_proxy_headers(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        api,
        "Settings",
        lambda: _stub_settings(
            api_processes=1,
            api_proxy_headers_enabled=False,
        ),
    )
    monkeypatch.setattr(
        api,
        "run",
        lambda command, *, cwd, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    api.run_start(processes=1)

    command = captured["command"]
    assert "--no-proxy-headers" in command
    assert "--proxy-headers" not in command
    assert "--forwarded-allow-ips" not in command
    assert "--workers" not in command


def test_dev_command_ignores_ade_api_processes_env(monkeypatch):
    captured: dict[str, object] = {}
    runner = CliRunner()

    monkeypatch.setattr(
        api,
        "run_dev",
        lambda *, host=None, processes=None: captured.update(
            {"host": host, "processes": processes}
        ),
    )

    result = runner.invoke(
        api.app,
        ["dev"],
        env={"ADE_API_PROCESSES": "7"},
    )

    assert result.exit_code == 0
    assert captured["processes"] is None


def test_start_command_still_reads_ade_api_processes_env(monkeypatch):
    captured: dict[str, object] = {}
    runner = CliRunner()

    monkeypatch.setattr(
        api,
        "run_start",
        lambda *, host=None, processes=None: captured.update(
            {"host": host, "processes": processes}
        ),
    )

    result = runner.invoke(
        api.app,
        ["start"],
        env={"ADE_API_PROCESSES": "6"},
    )

    assert result.exit_code == 0
    assert captured["processes"] == 6
