from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from ade_worker.paths import PathManager
from ade_worker.worker import SubprocessResult, Worker
import ade_worker.worker as worker_module


class _Layout:
    def __init__(self, root: Path) -> None:
        self.workspaces_dir = root / "workspaces"
        self.configs_dir = root / "workspaces"
        self.runs_dir = root / "runs"
        self.documents_dir = root / "workspaces"
        self.venvs_dir = root / "venvs"


class _Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def run(self, cmd, **kwargs) -> SubprocessResult:  # noqa: ANN001
        scope = str(kwargs["scope"])
        self.calls.append((scope, list(cmd)))
        if scope == "environment.venv":
            venv_dir = Path(cmd[-1])
            python_bin = (
                venv_dir / "Scripts" / "python.exe"
                if os.name == "nt"
                else venv_dir / "bin" / "python"
            )
            python_bin.parent.mkdir(parents=True, exist_ok=True)
            if not python_bin.exists():
                os.symlink(sys.executable, python_bin)
        return SubprocessResult(exit_code=0, timed_out=False, duration_seconds=0.01)


def test_build_environment_installs_config_in_editable_mode(monkeypatch, tmp_path: Path) -> None:
    layout = _Layout(tmp_path)
    paths = PathManager(layout=layout, pip_cache_root=tmp_path / "cache" / "pip")
    runner = _Runner()
    settings = SimpleNamespace(
        worker_env_build_timeout_seconds=120,
        worker_lease_seconds=30,
    )

    worker = Worker(
        settings=settings,  # type: ignore[arg-type]
        engine=object(),  # type: ignore[arg-type]
        session_factory=lambda: None,  # type: ignore[arg-type]
        worker_id="worker-test",
        paths=paths,
        runner=runner,  # type: ignore[arg-type]
        storage=object(),
    )

    workspace_id = "workspace-a"
    configuration_id = "config-a"
    env_id = "env-a"
    config_dir = paths.config_package_dir(workspace_id, configuration_id)
    config_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _fake_session_scope(_session_factory):  # noqa: ANN001
        yield object()

    monkeypatch.setattr(worker_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(worker_module.db, "ack_environment_success", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker_module.db, "record_environment_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        worker_module.subprocess,
        "check_output",
        lambda *args, **kwargs: "1.7.9\n",
    )
    monkeypatch.setattr(Worker, "_uv_bin", lambda self: "uv")

    result = worker._build_environment(
        env={
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "deps_digest": "sha256:abcd",
        },
        env_id=env_id,
        run_claim=None,
    )

    assert result.success is True
    scopes = [scope for scope, _cmd in runner.calls]
    assert scopes == ["environment.venv", "environment.config"]
    assert runner.calls[1][1][-2:] == ["-e", str(config_dir)]
