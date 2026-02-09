from __future__ import annotations

from typer.testing import CliRunner

from ade_cli import worker


def test_worker_run_tests_unit_scrubs_ade_env(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://runtime")
    monkeypatch.setenv("ADE_TEST_DATABASE_URL", "postgresql+psycopg://integration")
    monkeypatch.setattr(
        worker,
        "run",
        lambda command, *, cwd, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    runner = CliRunner()
    result = runner.invoke(worker.app, ["test"])

    assert result.exit_code == 0
    env = captured["env"]
    assert "ADE_DATABASE_URL" not in env
    assert "ADE_TEST_DATABASE_URL" not in env


def test_worker_run_tests_integration_preserves_ade_test_env(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setenv("ADE_DATABASE_URL", "postgresql+psycopg://runtime")
    monkeypatch.setenv("ADE_TEST_DATABASE_URL", "postgresql+psycopg://integration")
    monkeypatch.setattr(
        worker,
        "run",
        lambda command, *, cwd, env=None: captured.update(
            {"command": list(command), "cwd": cwd, "env": env}
        ),
    )

    runner = CliRunner()
    result = runner.invoke(worker.app, ["test", "integration"])

    assert result.exit_code == 0
    env = captured["env"]
    assert env["ADE_TEST_DATABASE_URL"] == "postgresql+psycopg://integration"
    assert "ADE_DATABASE_URL" not in env


def test_worker_run_tests_integration_requires_test_database_url(monkeypatch):
    monkeypatch.delenv("ADE_TEST_DATABASE_URL", raising=False)

    runner = CliRunner()
    result = runner.invoke(worker.app, ["test", "integration"])

    assert result.exit_code == 1
    assert "ADE_TEST_DATABASE_URL" in result.output
