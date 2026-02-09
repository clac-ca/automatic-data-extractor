from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ade_api.features.configs.storage import ConfigStorage


def test_templates_materialize_and_load(
    tmp_path: Path,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")
    workspace_id = uuid4()
    configuration_id = uuid4()

    storage.materialize_from_template(
        workspace_id=workspace_id,
        configuration_id=configuration_id,
    )

    config_path = storage.config_path(workspace_id, configuration_id)
    assert (config_path / "src" / "ade_config" / "__init__.py").is_file()
    assert config_path.exists()
