from __future__ import annotations

import sys
from pathlib import Path

import pytest
from ade_engine.config.loader import load_config_runtime

from ade_api.features.configs.storage import ConfigStorage


def _clear_config_imports(prefix: str = "ade_config") -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name)


@pytest.mark.parametrize("template_id", ["default", "sandbox"])
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
    manifest_path = config_path / "src" / "ade_config" / "manifest.toml"

    monkeypatch.syspath_prepend(str(config_path / "src"))
    _clear_config_imports()
    runtime = load_config_runtime("ade_config", manifest_path=manifest_path)
    manifest = runtime.manifest.model

    assert manifest.schema_id == "ade.manifest/v1"
    assert [col.name for col in manifest.columns]
    assert runtime.columns
