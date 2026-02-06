from __future__ import annotations

from pathlib import Path

from ade_cli.local_dev import build_local_profile, ensure_local_env


def test_build_local_profile_is_deterministic(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-a"
    repo_root.mkdir()

    first = build_local_profile(repo_root=repo_root)
    second = build_local_profile(repo_root=repo_root)

    assert first == second
    assert first.project_name
    assert first.profile_id


def test_build_local_profile_changes_with_repo_path(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    profile_a = build_local_profile(repo_root=repo_a)
    profile_b = build_local_profile(repo_root=repo_b)

    assert profile_a.profile_id != profile_b.profile_id
    assert profile_a.project_name != profile_b.project_name


def test_ensure_local_env_writes_and_force_regenerates(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-a"
    repo_root.mkdir()
    env_path = tmp_path / ".env"

    first = ensure_local_env(repo_root=repo_root, path=env_path)
    assert first.wrote_file is True
    assert env_path.exists()

    original = env_path.read_text(encoding="utf-8")
    env_path.write_text(original.replace("ADE_WEB_PORT=", "ADE_WEB_PORT=39999"), encoding="utf-8")

    second = ensure_local_env(repo_root=repo_root, path=env_path)
    assert second.wrote_file is False
    assert "ADE_WEB_PORT=39999" in env_path.read_text(encoding="utf-8")

    third = ensure_local_env(repo_root=repo_root, path=env_path, force=True)
    assert third.wrote_file is True
    assert "ADE_WEB_PORT=39999" not in env_path.read_text(encoding="utf-8")


def test_ensure_local_env_refreshes_when_profile_mismatch(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-a"
    repo_root.mkdir()
    env_path = tmp_path / ".env"

    first = ensure_local_env(repo_root=repo_root, path=env_path)
    assert first.wrote_file is True

    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            f"ADE_LOCAL_PROFILE_ID={first.profile.profile_id}",
            "ADE_LOCAL_PROFILE_ID=wrong-profile",
        ),
        encoding="utf-8",
    )

    second = ensure_local_env(repo_root=repo_root, path=env_path)
    assert second.wrote_file is True
    assert (
        f"ADE_LOCAL_PROFILE_ID={first.profile.profile_id}"
        in env_path.read_text(encoding="utf-8")
    )
