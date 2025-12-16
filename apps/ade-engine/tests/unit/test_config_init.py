from __future__ import annotations

from pathlib import Path

from ade_engine.cli.config import init_config


def test_config_init_scaffolds_template(tmp_path: Path) -> None:
    target = tmp_path / "config"
    init_config(target_dir=target, package_name="ade_config", layout="src", force=False)

    assert (target / "pyproject.toml").is_file()
    assert (target / "src" / "ade_config" / "__init__.py").is_file()
