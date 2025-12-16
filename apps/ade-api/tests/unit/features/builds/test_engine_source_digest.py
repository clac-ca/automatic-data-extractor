from __future__ import annotations

from pathlib import Path

from ade_api.features.builds.fingerprint import compute_engine_source_digest


def test_engine_source_digest_none_for_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert compute_engine_source_digest(str(missing)) is None


def test_engine_source_digest_changes_on_file_change(tmp_path: Path) -> None:
    root = tmp_path / "engine"
    (root / "src" / "ade_engine").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='ade-engine'\nversion='0.0.0'\n", encoding="utf-8")
    target = root / "src" / "ade_engine" / "mod.py"
    target.write_text("x = 1\n", encoding="utf-8")

    first = compute_engine_source_digest(str(root))
    assert first

    target.write_text("x = 2\n", encoding="utf-8")
    second = compute_engine_source_digest(str(root))
    assert second
    assert first != second

