from __future__ import annotations

import signal

import pytest
from typer.testing import CliRunner

import cli

runner = CliRunner()


def _empty_service_map() -> dict[str, set[int]]:
    return {"api": set(), "worker": set(), "web": set()}


def _disable_runtime_preflight(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_assert_no_running_ade_services", lambda: None)


def test_dev_warns_when_api_process_env_is_set(monkeypatch):
    captured: dict[str, object] = {}

    _disable_runtime_preflight(monkeypatch)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)

    def _fake_spawn(commands, *, cwd):
        captured["commands"] = commands
        captured["cwd"] = cwd

    monkeypatch.setattr(cli, "_spawn_processes", _fake_spawn)

    result = runner.invoke(
        cli.app,
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

    def _fake_spawn(commands, *, cwd):
        captured["commands"] = commands
        captured["cwd"] = cwd

    monkeypatch.setattr(cli, "_spawn_processes", _fake_spawn)

    result = runner.invoke(
        cli.app,
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


def test_start_does_not_emit_legacy_env_warnings(monkeypatch):
    _disable_runtime_preflight(monkeypatch)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)
    monkeypatch.setattr(cli, "_spawn_processes", lambda commands, *, cwd: None)

    result = runner.invoke(
        cli.app,
        ["start", "--services", "api", "--no-migrate"],
        env={
            "ADE_API_WORKERS": "2",
            "ADE_WORKER_CONCURRENCY": "8",
        },
    )

    assert result.exit_code == 0
    assert "ADE_API_WORKERS is no longer supported" not in result.output
    assert "ADE_WORKER_CONCURRENCY is no longer supported" not in result.output


def test_stop_no_matching_processes_returns_noop(monkeypatch):
    monkeypatch.setattr(cli, "_list_ade_service_pids", lambda: _empty_service_map())

    result = runner.invoke(cli.app, ["stop"])

    assert result.exit_code == 0
    assert "nothing to stop" in result.output


def test_stop_sends_sigterm_and_waits(monkeypatch):
    calls: list[tuple[int, set[int]]] = []

    monkeypatch.setattr(
        cli,
        "_list_ade_service_pids",
        lambda: {"api": {101}, "worker": {102}, "web": set()},
    )

    def _fake_signal(pids: set[int], signum: int) -> None:
        calls.append((signum, set(pids)))

    monkeypatch.setattr(cli, "_signal_pids", _fake_signal)
    monkeypatch.setattr(cli, "_wait_for_pids_exit", lambda pids, timeout: set())

    result = runner.invoke(cli.app, ["stop", "--timeout", "1"])

    assert result.exit_code == 0
    assert calls == [(signal.SIGTERM, {101, 102})]
    assert "ADE services stopped" in result.output


def test_stop_timeout_sends_sigkill(monkeypatch):
    calls: list[tuple[int, set[int]]] = []
    wait_calls: list[set[int]] = []

    monkeypatch.setattr(
        cli,
        "_list_ade_service_pids",
        lambda: {"api": {11, 12}, "worker": set(), "web": set()},
    )

    def _fake_signal(pids: set[int], signum: int) -> None:
        calls.append((signum, set(pids)))

    def _fake_wait(pids: set[int], timeout: float) -> set[int]:
        wait_calls.append(set(pids))
        if len(wait_calls) == 1:
            return {12}
        return set()

    monkeypatch.setattr(cli, "_signal_pids", _fake_signal)
    monkeypatch.setattr(cli, "_wait_for_pids_exit", _fake_wait)

    result = runner.invoke(cli.app, ["stop", "--timeout", "0.5"])

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

    result = runner.invoke(
        cli.app,
        ["restart", "--services", "worker", "--no-migrate", "--timeout", "7"],
    )

    assert result.exit_code == 0
    assert calls == [
        ("stop", 7.0),
        ("run", "start", "worker", False),
    ]


@pytest.mark.parametrize("command", ["start", "dev"])
def test_start_and_dev_fail_fast_when_ade_processes_exist(monkeypatch, command):
    monkeypatch.setattr(
        cli,
        "_list_ade_service_pids",
        lambda: {"api": {2101}, "worker": set(), "web": set()},
    )

    result = runner.invoke(
        cli.app,
        [command, "--services", "api", "--no-migrate"],
    )

    assert result.exit_code == 1
    assert "ADE service processes already running" in result.output


def test_process_discovery_deduplicates_and_handles_partial_matches(monkeypatch):
    def _fake_find(patterns: tuple[str, ...]) -> set[int]:
        if patterns == cli.API_PROCESS_PATTERNS:
            return {1000}
        if patterns == cli.WORKER_PROCESS_PATTERNS:
            return {2000, 2001, 2002}
        if patterns == cli.WEB_PROCESS_PATTERNS:
            return {3000}
        return set()

    monkeypatch.setattr(cli, "_find_matching_pids", _fake_find)

    service_pids = cli._list_ade_service_pids()

    assert service_pids["api"] == {1000}
    assert service_pids["worker"] == {2000, 2001, 2002}
    assert service_pids["web"] == {3000}
    assert cli._all_ade_service_pids(service_pids) == {1000, 2000, 2001, 2002, 3000}
