from __future__ import annotations

from typer.testing import CliRunner

from ade_cli import web

runner = CliRunner()


def test_open_uses_public_web_url(monkeypatch):
    called: dict[str, str] = {}
    monkeypatch.setenv("ADE_PUBLIC_WEB_URL", "http://127.0.0.1:30087")
    monkeypatch.delenv("ADE_WEB_PORT", raising=False)

    def _launch(url: str) -> int:
        called["url"] = url
        return 0

    monkeypatch.setattr(web.typer, "launch", _launch)

    result = runner.invoke(web.app, ["open"])

    assert result.exit_code == 0
    assert called["url"] == "http://127.0.0.1:30087"
    assert "http://127.0.0.1:30087" in result.output


def test_open_falls_back_to_port_when_public_web_url_invalid(monkeypatch):
    called: dict[str, str] = {}
    monkeypatch.setenv("ADE_PUBLIC_WEB_URL", "127.0.0.1:30087")
    monkeypatch.setenv("ADE_WEB_PORT", "31087")

    def _launch(url: str) -> int:
        called["url"] = url
        return 0

    monkeypatch.setattr(web.typer, "launch", _launch)

    result = runner.invoke(web.app, ["open"])

    assert result.exit_code == 0
    assert called["url"] == "http://127.0.0.1:31087"
    assert "warning: ADE_PUBLIC_WEB_URL must be a full origin" in result.output


def test_open_errors_on_invalid_web_port(monkeypatch):
    monkeypatch.delenv("ADE_PUBLIC_WEB_URL", raising=False)
    monkeypatch.setenv("ADE_WEB_PORT", "not-a-port")
    monkeypatch.setattr(web.typer, "launch", lambda url: 0)

    result = runner.invoke(web.app, ["open"])

    assert result.exit_code == 1
    assert "ADE_WEB_PORT must be an integer between 1 and 65535" in result.output


def test_open_prints_manual_hint_when_launcher_fails(monkeypatch):
    monkeypatch.delenv("ADE_PUBLIC_WEB_URL", raising=False)
    monkeypatch.setenv("ADE_WEB_PORT", "30087")
    monkeypatch.setattr(web.typer, "launch", lambda url: 1)

    result = runner.invoke(web.app, ["open"])

    assert result.exit_code == 0
    assert "warning: failed to open browser automatically" in result.output
    assert "Open manually: http://127.0.0.1:30087" in result.output
