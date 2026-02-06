from __future__ import annotations

from typer.testing import CliRunner

from ade_cli import main as cli
from ade_cli.main import app

runner = CliRunner()


def test_dev_runs_selected_services(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "_maybe_run_migrations",
        lambda selected, migrate: calls.update({"migrate": (selected, migrate)}),
    )
    monkeypatch.setattr(
        cli,
        "run_many",
        lambda processes, *, cwd: calls.update(
            {
                "process_names": [proc.name for proc in processes],
                "cwd": cwd,
            }
        ),
    )

    result = runner.invoke(app, ["dev", "--services", "api,worker", "--no-migrate"])

    assert result.exit_code == 0
    assert calls["migrate"] == (["api", "worker"], False)
    assert calls["process_names"] == ["api", "worker"]


def test_start_defaults_to_all_services(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "_maybe_run_migrations",
        lambda selected, migrate: calls.update({"migrate": (selected, migrate)}),
    )
    monkeypatch.setattr(
        cli,
        "run_many",
        lambda processes, *, cwd: calls.update(
            {
                "process_names": [proc.name for proc in processes],
                "cwd": cwd,
            }
        ),
    )

    result = runner.invoke(app, ["start", "--no-migrate"])

    assert result.exit_code == 0
    assert calls["migrate"] == (["api", "worker", "web"], False)
    assert calls["process_names"] == ["api", "worker", "web"]


def test_unknown_service_fails():
    result = runner.invoke(app, ["dev", "--services", "api,nope"])

    assert result.exit_code == 1
    assert "unknown service" in result.output


def test_reset_requires_yes_flag():
    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 1
    assert "reset requires --yes" in result.output
