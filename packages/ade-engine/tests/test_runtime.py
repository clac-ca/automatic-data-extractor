from __future__ import annotations

from pathlib import Path

from ade_engine.runtime import load_config_manifest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "templates" / "config-packages" / "default" / "src" / "ade_config" / "manifest.json"


def test_load_config_manifest_from_path() -> None:
    manifest = load_config_manifest(manifest_path=MANIFEST_PATH)

    assert manifest["config"]["display_name"] == "ADE Config Package"
