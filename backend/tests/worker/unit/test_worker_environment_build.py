from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from ade_worker.paths import PathManager
from ade_worker.worker import EventLog, SubprocessResult, Worker
from ade_worker import db as worker_db


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
    paths = PathManager(
        layout=layout,
        worker_runs_root=layout.runs_dir,
        worker_venvs_root=layout.venvs_dir,
        worker_pip_cache_root=tmp_path / "cache" / "pip",
    )
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
    config_dir = paths.config_package_dir(workspace_id, configuration_id)
    config_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Worker, "_uv_bin", lambda self: "uv")
    monkeypatch.setattr(Worker, "_heartbeat_run", lambda self, *, run_id, now=None: True)

    event_log = EventLog(tmp_path / "events.ndjson")
    claim = worker_db.RunClaim(id="run-a", attempt_count=1, max_attempts=3)

    result = worker._ensure_local_venv(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:abcd",
        run_claim=claim,
        event_log=event_log,
        ctx={
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "deps_digest": "sha256:abcd",
            "environment_id": None,
        },
    )

    assert result.python_bin is not None
    assert result.python_bin.exists()
    assert result.run_lost is False
    assert result.error_message is None
    scopes = [scope for scope, _cmd in runner.calls]
    assert scopes == ["environment.venv", "environment.config"]
    assert runner.calls[1][1][-2:] == ["-e", str(config_dir)]
