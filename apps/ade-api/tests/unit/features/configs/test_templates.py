from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.features.configs.storage import ConfigStorage


@pytest.mark.parametrize("template_id", ["default"])
@pytest.mark.asyncio
async def test_templates_materialize_and_load(
    tmp_path: Path,
    template_id: str,
) -> None:
    storage = ConfigStorage(configs_root=tmp_path / "configs")

    await storage.materialize_from_template(
        workspace_id="ws",
        configuration_id=f"cfg-{template_id}",
        template_id=template_id,
    )

    config_path = storage.config_path("ws", f"cfg-{template_id}")
    assert (config_path / "src" / "ade_config" / "__init__.py").is_file()
    assert config_path.exists()
