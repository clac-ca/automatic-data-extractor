from __future__ import annotations

import signal

import pytest
from typer.testing import CliRunner

from ade_cli.root import app
from ade_cli.root import shared as cli

runner = CliRunner()


def _disable_runtime_preflight(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_assert_no_running_ade_services", lambda: None)


def test_dev_warns_when_api_process_env_is_set(monkeypatch):
    captured: dict[str, object] = {}

    _disable_runtime_preflight(monkeypatch)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)

    def _fake_spawn(commands, *, cwd, mode, selected):
        captured["commands"] = commands
        captured["cwd"] = cwd
        captured["mode"] = mode
        captured["selected"] = selected

    monkeypatch.setattr(cli, "_spawn_processes", _fake_spawn)

    result = runner.invoke(app,
        ["dev", "--services", "api", "--no-migrate"],
        env={"ADE_API_PROCESSES": "4"},
    )

    assert result.exit_code == 0
    assert "ADE_API_PROCESSES is ignored by `ade dev`" in result.output
    assert "api.processes: 1 (dev reload mode" in result.output
    commands = captured["commands"]
    assert "api" in commands


def test_start_banner_includes_effective_process_and_concurrency(monkeypatch):
    captured: dict[str, object] = {}

    _disable_runtime_preflight(monkeypatch)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)

    def _fake_spawn(commands, *, cwd, mode, selected):
        captured["commands"] = commands
        captured["cwd"] = cwd
        captured["mode"] = mode
        captured["selected"] = selected

    monkeypatch.setattr(cli, "_spawn_processes", _fake_spawn)

    result = runner.invoke(app,
        ["start", "--services", "api,worker", "--no-migrate"],
        env={
            "ADE_API_PROCESSES": "3",
            "ADE_WORKER_RUN_CONCURRENCY": "6",
        },
    )

    assert result.exit_code == 0
    assert "mode: start" in result.output
    assert "api.processes: 3" in result.output
    assert "worker.run_concurrency: 6" in result.output
    commands = captured["commands"]
    assert "api" in commands
    assert "worker" in commands


def test_stop_no_tracked_processes_returns_noop(monkeypatch):
    monkeypatch.setattr(cli, "_load_state", lambda: None)

    result = runner.invoke(app, ["stop"])

    assert result.exit_code == 0
    assert "nothing to stop" in result.output


def test_stop_sends_sigterm_and_waits(monkeypatch):
    calls: list[tuple[int, set[int]]] = []

    monkeypatch.setattr(
        cli,
        "_load_state",
        lambda: {
            "processes": {
                "api": {"pid": 101},
                "worker": {"pid": 102},
            }
        },
    )
    monkeypatch.setattr(
        cli,
        "_extract_live_service_pids",
        lambda state: {"api": 101, "worker": 102},
    )

    def _fake_signal(pids: set[int], signum: int) -> None:
        calls.append((signum, set(pids)))

    monkeypatch.setattr(cli, "_signal_pids", _fake_signal)
    monkeypatch.setattr(cli, "_wait_for_pids_exit", lambda pids, timeout: set())

    result = runner.invoke(app, ["stop", "--timeout", "1"])

    assert result.exit_code == 0
    assert calls == [(signal.SIGTERM, {101, 102})]
    assert "ADE services stopped" in result.output


def test_stop_timeout_sends_sigkill(monkeypatch):
    calls: list[tuple[int, set[int]]] = []
    wait_calls: list[set[int]] = []

    monkeypatch.setattr(
        cli,
        "_load_state",
        lambda: {
            "processes": {
                "api": {"pid": 11},
                "worker": {"pid": 12},
            }
        },
    )
    monkeypatch.setattr(cli, "_extract_live_service_pids", lambda state: {"api": 11, "worker": 12})

    def _fake_signal(pids: set[int], signum: int) -> None:
        calls.append((signum, set(pids)))

    def _fake_wait(pids: set[int], timeout: float) -> set[int]:
        wait_calls.append(set(pids))
        if len(wait_calls) == 1:
            return {12}
        return set()

    monkeypatch.setattr(cli, "_signal_pids", _fake_signal)
    monkeypatch.setattr(cli, "_wait_for_pids_exit", _fake_wait)

    result = runner.invoke(app, ["stop", "--timeout", "0.5"])

    assert result.exit_code == 0
    assert calls == [
        (signal.SIGTERM, {11, 12}),
        (signal.SIGKILL, {12}),
    ]
    assert wait_calls == [{11, 12}, {12}]
    assert "force-stopped" in result.output


def test_restart_runs_stop_then_start(monkeypatch):
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        cli,
        "_stop_ade_services",
        lambda *, timeout: calls.append(("stop", timeout)),
    )
    monkeypatch.setattr(
        cli,
        "_run_root_mode",
        lambda *, mode, services, migrate: calls.append(("run", mode, services, migrate)),
    )

    result = runner.invoke(app,
        ["restart", "--services", "worker", "--no-migrate", "--timeout", "7"],
    )

    assert result.exit_code == 0
    assert calls == [
        ("stop", 7.0),
        ("run", "start", "worker", False),
    ]


@pytest.mark.parametrize("command", ["start", "dev"])
def test_start_and_dev_fail_fast_when_tracked_processes_exist(monkeypatch, command):
    monkeypatch.setattr(cli, "_load_state", lambda: {"processes": {"api": {"pid": 2101}}})
    monkeypatch.setattr(cli, "_extract_live_service_pids", lambda state: {"api": 2101})

    result = runner.invoke(app,
        [command, "--services", "api", "--no-migrate"],
    )

    assert result.exit_code == 1
    assert "ADE service processes already running" in result.output


def test_status_shows_running_and_exited_processes(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_load_state",
        lambda: {
            "mode": "dev",
            "started_at": "2026-01-01T00:00:00+00:00",
            "services": ["api", "worker"],
            "processes": {
                "api": {"pid": 4001},
                "worker": {"pid": 4002},
            },
        },
    )
    monkeypatch.setattr(cli, "_extract_live_service_pids", lambda state: {"api": 4001})

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "mode: dev" in result.output
    assert "api: pid=4001 running" in result.output
    assert "worker: pid=4002 exited" in result.output


def test_assert_no_running_services_cleans_stale_state(monkeypatch):
    called = {"cleared": False}

    monkeypatch.setattr(cli, "_load_state", lambda: {"processes": {"api": {"pid": 9001}}})
    monkeypatch.setattr(cli, "_extract_live_service_pids", lambda state: {})
    monkeypatch.setattr(cli, "_clear_state", lambda: called.__setitem__("cleared", True))

    cli._assert_no_running_ade_services()

    assert called["cleared"] is True
