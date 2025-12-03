from __future__ import annotations

import sys

import pytest
import typer

from ade_tools.commands import tests as tests_cmd


def test_conflicting_flags_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tests_cmd.common, "refresh_paths", lambda: None)

    with pytest.raises(typer.Exit) as excinfo:
        tests_cmd.run_tests(backend_only=True, frontend_only=True)

    assert excinfo.value.exit_code == 1


def test_backend_suite_runs_when_selected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    backend_dir = tmp_path / "apps" / "ade-api"
    backend_src = backend_dir / "src" / "ade_api"
    backend_src.mkdir(parents=True)

    commands: list[tuple[list[str], object]] = []
    monkeypatch.setattr(tests_cmd.common, "refresh_paths", lambda: None)
    monkeypatch.setattr(tests_cmd.common, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(tests_cmd.common, "BACKEND_SRC", backend_src)
    monkeypatch.setattr(tests_cmd.common, "FRONTEND_DIR", tmp_path / "apps" / "ade-web")
    monkeypatch.setattr(tests_cmd.common, "require_python_module", lambda *_, **__: None)

    def fake_run(cmd, cwd=None, env=None):
        commands.append((list(cmd), cwd))

    monkeypatch.setattr(tests_cmd.common, "run", fake_run)

    tests_cmd.run_tests(frontend=False)

    assert commands == [([sys.executable, "-m", "pytest", "-q"], backend_dir)]


def test_frontend_suite_runs_when_script_present(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    frontend_dir = tmp_path / "apps" / "ade-web"
    frontend_dir.mkdir(parents=True)

    commands: list[tuple[list[str], object]] = []
    monkeypatch.setattr(tests_cmd.common, "refresh_paths", lambda: None)
    monkeypatch.setattr(tests_cmd.common, "FRONTEND_DIR", frontend_dir)
    monkeypatch.setattr(tests_cmd.common, "BACKEND_SRC", tmp_path / "missing-backend")
    monkeypatch.setattr(tests_cmd.common, "npm_path", lambda: "npm-bin")
    monkeypatch.setattr(tests_cmd.common, "ensure_node_modules", lambda *_, **__: None)
    monkeypatch.setattr(tests_cmd.common, "load_frontend_package_json", lambda: {"scripts": {"test": "vitest"}})

    def fake_run(cmd, cwd=None, env=None):
        commands.append((list(cmd), cwd))

    monkeypatch.setattr(tests_cmd.common, "run", fake_run)

    tests_cmd.run_tests(backend=False, frontend=True)

    assert commands == [(["npm-bin", "run", "test"], frontend_dir)]


def test_exit_when_no_suites_run(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    frontend_dir = tmp_path / "apps" / "ade-web"
    frontend_dir.mkdir(parents=True)

    monkeypatch.setattr(tests_cmd.common, "refresh_paths", lambda: None)
    monkeypatch.setattr(tests_cmd.common, "FRONTEND_DIR", frontend_dir)
    monkeypatch.setattr(tests_cmd.common, "BACKEND_SRC", tmp_path / "missing-backend")
    monkeypatch.setattr(tests_cmd.common, "load_frontend_package_json", lambda: {"scripts": {}})

    with pytest.raises(typer.Exit) as excinfo:
        tests_cmd.run_tests(backend=False, frontend=True)

    assert excinfo.value.exit_code == 1
