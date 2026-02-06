from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from ade_worker.gc import gc_local_venv_cache
from ade_worker.paths import PathManager


class _Layout:
    def __init__(self, root: Path, runs_root: Path | None = None) -> None:
        self.workspaces_dir = root / "workspaces"
        self.configs_dir = self.workspaces_dir
        self.documents_dir = self.workspaces_dir
        self.runs_dir = runs_root or (root / "runs")
        self.venvs_dir = root / "venvs"
        self.pip_cache_dir = root / "cache" / "pip"


def _uuid() -> str:
    return str(uuid4())


def _make_env_dir(
    paths: PathManager,
    *,
    workspace_id: str,
    configuration_id: str,
    deps_digest: str,
    env_id: str,
) -> Path:
    env_path = paths.environment_root(workspace_id, configuration_id, deps_digest, env_id)
    env_path.mkdir(parents=True, exist_ok=True)
    marker = env_path / ".ready"
    marker.write_text("ready")
    return env_path


def _make_paths(tmp_path: Path) -> PathManager:
    data_root = tmp_path / "data"
    layout = _Layout(data_root, tmp_path / "runs")
    return PathManager(
        layout=layout,
        worker_runs_root=layout.runs_dir,
        worker_venvs_root=layout.venvs_dir,
        worker_pip_cache_root=layout.pip_cache_dir,
    )


def test_gc_local_cache_skips_recent_environment(tmp_path: Path) -> None:
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = _make_paths(tmp_path)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()
    env_path = _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:abc",
        env_id=env_id,
    )
    marker = env_path / ".ready"
    recent = now - timedelta(days=2)
    os.utime(marker, (recent.timestamp(), recent.timestamp()))

    result = gc_local_venv_cache(paths=paths, now=now, cache_ttl_days=30)

    assert result.deleted == 0
    assert result.skipped == 1
    assert env_path.exists()


def test_gc_local_cache_deletes_cold_environment(tmp_path: Path) -> None:
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = _make_paths(tmp_path)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()

    env_path = _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:def",
        env_id=env_id,
    )
    marker = env_path / ".ready"
    cold = now - timedelta(days=45)
    os.utime(marker, (cold.timestamp(), cold.timestamp()))

    result = gc_local_venv_cache(paths=paths, now=now, cache_ttl_days=30)

    assert result.deleted == 1
    assert not env_path.exists()


def test_gc_local_cache_idempotent(tmp_path: Path) -> None:
    now = datetime(2025, 1, 10, 12, 0, 0)
    paths = _make_paths(tmp_path)

    workspace_id = _uuid()
    configuration_id = _uuid()
    env_id = _uuid()

    env_path = _make_env_dir(
        paths,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:ghi",
        env_id=env_id,
    )
    marker = env_path / ".ready"
    cold = now - timedelta(days=45)
    os.utime(marker, (cold.timestamp(), cold.timestamp()))

    first = gc_local_venv_cache(paths=paths, now=now, cache_ttl_days=1)
    second = gc_local_venv_cache(paths=paths, now=now, cache_ttl_days=1)

    assert first.deleted == 1
    assert second.deleted == 0
