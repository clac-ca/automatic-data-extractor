from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import ade_engine.cli.config as config_cli


def test_config_init_scaffolds_template(tmp_path: Path) -> None:
    target = tmp_path / "config"
    config_cli.init_config(target_dir=target, package_name="ade_config", layout="src", force=False)

    assert (target / "pyproject.toml").is_file()
    assert (target / "src" / "ade_config" / "__init__.py").is_file()
    assert not (target / ".ruff_cache").exists()


def test_config_init_ignores_ruff_cache(tmp_path: Path, monkeypatch) -> None:
    template_root = tmp_path / "template"
    (template_root / ".ruff_cache").mkdir(parents=True)
    (template_root / ".ruff_cache" / "ignored.txt").write_text("ignore me", encoding="utf-8")

    pkg_dir = template_root / "src" / "ade_config"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    (template_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "ade-config-template"',
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["src/ade_config"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeTemplateRoot:
        def __init__(self, root: Path) -> None:
            self._root = root

        def joinpath(self, *_parts: str) -> Path:
            return self._root

    @contextmanager
    def _as_file(path: Path):
        yield path

    monkeypatch.setattr(config_cli.resources, "files", lambda _pkg: _FakeTemplateRoot(template_root))
    monkeypatch.setattr(config_cli.resources, "as_file", lambda traversable: _as_file(traversable))

    target = tmp_path / "out"
    config_cli.init_config(target_dir=target, package_name="ade_config", layout="src", force=False)

    assert (target / "pyproject.toml").is_file()
    assert (target / "src" / "ade_config" / "__init__.py").is_file()
    assert not (target / ".ruff_cache").exists()
