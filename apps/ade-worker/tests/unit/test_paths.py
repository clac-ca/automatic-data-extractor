from __future__ import annotations

from pathlib import Path

from ade_worker.paths import PathManager


def test_environment_path_is_stable(tmp_path: Path) -> None:
    paths = PathManager(tmp_path, tmp_path / "venvs")
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
