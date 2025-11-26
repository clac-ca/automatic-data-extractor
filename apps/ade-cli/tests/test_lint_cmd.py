from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

from ade_tools import cli
from ade_tools.commands import lint_cmd

runner = CliRunner()


def test_run_lint_uses_fix_flag(monkeypatch, tmp_path: Path) -> None:
    backend_dir = tmp_path / "apps" / "ade-api"
    backend_src = backend_dir / "src" / "ade_api"
    frontend_dir = tmp_path / "apps" / "ade-web"
    backend_src.mkdir(parents=True)
    frontend_dir.mkdir(parents=True)

    commands: list[tuple[list[str], Path | None]] = []
    monkeypatch.setattr(lint_cmd.common, "refresh_paths", lambda: None)
    monkeypatch.setattr(lint_cmd.common, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(lint_cmd.common, "BACKEND_SRC", backend_src)
    monkeypatch.setattr(lint_cmd.common, "FRONTEND_DIR", frontend_dir)
    monkeypatch.setattr(lint_cmd.common, "require_python_module", lambda *_, **__: None)
    monkeypatch.setattr(lint_cmd.shutil, "which", lambda *_, **__: None)
    monkeypatch.setattr(lint_cmd.common, "load_frontend_package_json", lambda: {"scripts": {"lint": "lint"}})
    monkeypatch.setattr(lint_cmd.common, "ensure_node_modules", lambda *_, **__: None)
    monkeypatch.setattr(lint_cmd.common, "npm_path", lambda: "npm-bin")

    def fake_run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
        commands.append((list(cmd), cwd))

    monkeypatch.setattr(lint_cmd.common, "run", fake_run)

    lint_cmd.run_lint(scope="all", fix=True)

    assert commands == [
        ([sys.executable, "-m", "ruff", "check", "--fix", "src/ade_api"], backend_dir),
        (["npm-bin", "run", "lint", "--", "--fix"], frontend_dir),
    ]


def test_cli_lint_accepts_fix(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(lint_cmd, "run_lint", lambda scope, fix: calls.append((scope, fix)))

    result = runner.invoke(cli.app, ["lint", "--fix"])

    assert result.exit_code == 0
    assert calls == [("all", True)]
