from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.features.configs.storage import ConfigStorage


@pytest.mark.parametrize("template_id", ["default"])
@pytest.mark.asyncio
async def test_templates_materialize_and_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_id: str,
) -> None:
    templates_root = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "ade_api"
        / "templates"
        / "config_packages"
    )
    storage = ConfigStorage(templates_root=templates_root, configs_root=tmp_path / "configs")

    await storage.materialize_from_template(
        workspace_id="ws",
        configuration_id=f"cfg-{template_id}",
        template_id=template_id,
    )

    config_path = storage.config_path("ws", f"cfg-{template_id}")
    assert (config_path / "src" / "ade_config" / "__init__.py").is_file()
    assert config_path.exists()
