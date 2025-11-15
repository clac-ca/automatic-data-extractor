from __future__ import annotations

import json
from pathlib import Path

from ade_engine.runtime import load_config_manifest, load_manifest_context

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_ROOT = REPO_ROOT / "apps" / "api" / "app" / "templates" / "config_packages"
MANIFEST_PATH = TEMPLATES_ROOT / "default" / "src" / "ade_config" / "manifest.json"


def test_load_config_manifest_from_path() -> None:
    manifest = load_config_manifest(manifest_path=MANIFEST_PATH)

    assert manifest["config"]["display_name"] == "ADE Config Package"


def test_load_manifest_context_returns_models(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {
                        "mapping_score_threshold": 0.6,
                        "detector_sample_size": 10,
                    },
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {},
                "columns": {
                    "order": ["member_id"],
                    "meta": {
                        "member_id": {
                            "label": "Member ID",
                            "script": "columns/member_id.py",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_manifest_context(manifest_path=manifest_path)

    assert context.model is not None
    assert context.column_order == ["member_id"]
    assert context.writer["mode"] == "row_streaming"
