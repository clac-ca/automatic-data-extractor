from __future__ import annotations

from typer.testing import CliRunner

from ade_cli import main as cli
from ade_cli.main import app

runner = CliRunner()


def test_dev_runs_selected_services(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "_preflight_runtime", lambda selected: None)
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


def test_dev_open_triggers_browser_helper(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "_preflight_runtime", lambda selected: None)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)
    monkeypatch.setattr(
        cli,
        "_maybe_open_browser",
        lambda *, selected, open_in_browser: calls.update(
            {"open": (selected, open_in_browser)}
        ),
    )
    monkeypatch.setattr(cli, "run_many", lambda processes, *, cwd: None)

    result = runner.invoke(
        app, ["dev", "--services", "api,web", "--no-migrate", "--open"]
    )

    assert result.exit_code == 0
    assert calls["open"] == (["api", "web"], True)


def test_start_defaults_to_all_services(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "_preflight_runtime", lambda selected: None)
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


def test_start_open_triggers_browser_helper(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "_preflight_runtime", lambda selected: None)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)
    monkeypatch.setattr(
        cli,
        "_maybe_open_browser",
        lambda *, selected, open_in_browser: calls.update(
            {"open": (selected, open_in_browser)}
        ),
    )
    monkeypatch.setattr(cli, "run_many", lambda processes, *, cwd: None)

    result = runner.invoke(app, ["start", "--no-migrate", "--open"])

    assert result.exit_code == 0
    assert calls["open"] == (["api", "worker", "web"], True)


def test_open_warns_when_web_not_selected(monkeypatch):
    def _fail_if_called(url: str) -> None:
        raise AssertionError("browser helper should not run when web service is excluded")

    monkeypatch.setattr(cli, "_preflight_runtime", lambda selected: None)
    monkeypatch.setattr(cli, "_maybe_run_migrations", lambda selected, migrate: None)
    monkeypatch.setattr(cli, "run_many", lambda processes, *, cwd: None)
    monkeypatch.setattr(cli, "_open_browser_when_ready", _fail_if_called)

    result = runner.invoke(
        app, ["dev", "--services", "api,worker", "--no-migrate", "--open"]
    )

    assert result.exit_code == 0
    assert "warning: --open ignored because web service is not selected." in result.output


def test_unknown_service_fails():
    result = runner.invoke(app, ["dev", "--services", "api,nope"])

    assert result.exit_code == 1
    assert "unknown service" in result.output


def test_reset_requires_yes_flag():
    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 1
    assert "reset requires --yes" in result.output


def test_dev_shows_infra_hint_when_runtime_env_missing(monkeypatch):
    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_SECRET_KEY", raising=False)
    monkeypatch.delenv("ADE_BLOB_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("ADE_BLOB_ACCOUNT_URL", raising=False)

    result = runner.invoke(app, ["dev", "--services", "api"])

    assert result.exit_code == 1
    assert "hint: run `cd backend && uv run ade infra up`." in result.output
