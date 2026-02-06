from __future__ import annotations

import io
import zipfile
from pathlib import Path
from uuid import uuid4

from ade_api.features.configs.storage import ConfigStorage


def test_templates_materialize_and_load(
    tmp_path: Path,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()
    storage.validate_path = lambda path: ([], "sha256:test")  # type: ignore[method-assign]

    storage.materialize_from_template(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
    )

    config_path = storage.config_path(workspace_id, configuration_id)
    assert (config_path / "src" / "ade_config" / "__init__.py").is_file()
    assert config_path.exists()


def test_import_archive_does_not_mutate_pyproject_dependencies(tmp_path: Path) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w") as zf:
        zf.writestr(
            "pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr("src/ade_config/__init__.py", "__all__ = []\n")

    storage.validate_path = lambda path: ([], "sha256:test")  # type: ignore[method-assign]
    storage.import_archive(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        archive=archive_bytes.getvalue(),
    )

    pyproject = storage.config_path(workspace_id, configuration_id) / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert "dependencies = [\"ade-engine\"]" in content
    assert "allow-direct-references" not in content
