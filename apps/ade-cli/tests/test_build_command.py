from __future__ import annotations

from pathlib import Path

import pytest
import typer

from ade_tools.commands import build, common


def test_build_requires_backend_and_dist(monkeypatch, tmp_path):
    frontend = tmp_path / "apps" / "ade-web"
    backend = tmp_path / "apps" / "ade-api" / "src" / "ade_api"
    frontend.mkdir(parents=True)
    backend.mkdir(parents=True)
    (frontend / "package.json").write_text("{}")
    (frontend / "node_modules").mkdir()

    calls: dict[str, object] = {}
    monkeypatch.setattr(common, "refresh_paths", lambda: calls.setdefault("refreshed", True))
    monkeypatch.setattr(common, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(common, "BACKEND_SRC", backend)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(common, "npm_path", lambda: "npm-bin")
    monkeypatch.setattr(common, "ensure_node_modules", lambda frontend_dir=None: calls.setdefault("ensured_node", True))
    monkeypatch.setattr(common, "run", lambda *args, **kwargs: calls.setdefault("ran_npm", True))

    with pytest.raises(typer.Exit):
        build.run_build()

    assert calls["refreshed"] is True
    assert calls["ensured_node"] is True
    assert calls["ran_npm"] is True


def test_build_copies_dist(monkeypatch, tmp_path):
    frontend = tmp_path / "apps" / "ade-web"
    backend = tmp_path / "apps" / "ade-api" / "src" / "ade_api"
    dist = frontend / "dist"
    target = backend / "web" / "static"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    frontend.mkdir(parents=True, exist_ok=True)
    backend.mkdir(parents=True, exist_ok=True)
    (frontend / "node_modules").mkdir(parents=True, exist_ok=True)
    (frontend / "package.json").write_text("{}")

    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(common, "BACKEND_SRC", backend)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(common, "npm_path", lambda: "npm-bin")
    monkeypatch.setattr(common, "ensure_node_modules", lambda frontend_dir=None: None)
    monkeypatch.setattr(common, "run", lambda *args, **kwargs: None)

    build.run_build()

    copied = target / "index.html"
    assert copied.exists()
    assert copied.read_text() == "<html></html>"
