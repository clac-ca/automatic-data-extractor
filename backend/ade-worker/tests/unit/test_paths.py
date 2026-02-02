from __future__ import annotations

from pathlib import Path

from ade_worker.paths import PathManager


class _Layout:
    def __init__(self, root: Path) -> None:
        self.workspaces_dir = root / "workspaces"
        self.configs_dir = self.workspaces_dir
        self.documents_dir = self.workspaces_dir
        self.runs_dir = root / "runs"
        self.venvs_dir = root / "venvs"
        self.pip_cache_dir = root / "cache" / "pip"


def test_environment_path_is_stable(tmp_path: Path) -> None:
    layout = _Layout(tmp_path)
    paths = PathManager(layout, layout.pip_cache_dir)
    path_a = paths.environment_root(
        workspace_id="ws-1",
        configuration_id="cfg-1",
        deps_digest="sha256:abc123",
        environment_id="env-1",
    )
    path_b = paths.environment_root(
        workspace_id="ws-1",
        configuration_id="cfg-1",
        deps_digest="sha256:abc123",
        environment_id="env-1",
    )
    assert path_a == path_b
    assert "deps-abc123" in path_a.as_posix()
