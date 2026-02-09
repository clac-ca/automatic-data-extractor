from __future__ import annotations

from pathlib import Path

from ade_api.features.configs.deps import compute_dependency_digest, has_engine_dependency


def test_dependency_digest_ignores_source_files(tmp_path: Path) -> None:
    root = tmp_path
    manifest = root / "pyproject.toml"
    manifest.write_text('[project]\nname = "demo"\n', encoding="utf-8")

    digest_initial = compute_dependency_digest(root)

    src_dir = root / "src" / "ade_config"
    src_dir.mkdir(parents=True)
    (src_dir / "hooks.py").write_text("print('hello')\n", encoding="utf-8")

    digest_after_source = compute_dependency_digest(root)
    assert digest_after_source == digest_initial

    manifest.write_text('[project]\nname = "demo"\ndependencies = ["pandas"]\n', encoding="utf-8")
    digest_after_manifest = compute_dependency_digest(root)

    assert digest_after_manifest != digest_initial


def test_has_engine_dependency_from_pyproject(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        (
            "[project]\n"
            "name = \"demo\"\n"
            "dependencies = [\"ade-engine==1.2.3\", \"pandas>=2.0\"]\n"
        ),
        encoding="utf-8",
    )

    assert has_engine_dependency(tmp_path) is True


def test_has_engine_dependency_from_requirements_file(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pandas==2.2.0\nade_engine>=1.0\n", encoding="utf-8")

    assert has_engine_dependency(tmp_path) is True
