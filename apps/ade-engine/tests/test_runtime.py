from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ade_engine.runtime import load_config_manifest, load_manifest_context


def test_load_config_manifest_from_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "config_script_api_version": "1",
                "info": {
                    "schema": "ade.manifest/v1.0",
                    "title": "Test Config",
                    "version": "1.0.0",
                },
                "engine": {
                    "defaults": {"mapping_score_threshold": 0.0},
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

    manifest = load_config_manifest(manifest_path=manifest_path)

    assert manifest["info"]["schema"] == "ade.manifest/v1.0"


def test_load_config_manifest_from_package(monkeypatch: Any, tmp_path: Path) -> None:
    package_dir = tmp_path / "fake_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    manifest_data = {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": "Test Config",
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {"mapping_score_threshold": 0.0},
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

    (package_dir / "manifest.json").write_text(
        json.dumps(manifest_data), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    manifest = load_config_manifest(package="fake_pkg", resource="manifest.json")

    assert manifest["info"]["schema"] == "ade.manifest/v1.0"


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


def test_manifest_with_before_save_hooks_validates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest_with_hooks.json"
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
                    "defaults": {},
                    "writer": {
                        "mode": "row_streaming",
                        "append_unmapped_columns": True,
                        "unmapped_prefix": "raw_",
                        "output_sheet": "Normalized",
                    },
                },
                "hooks": {
                    "on_before_save": [{"script": "hooks/on_before_save.py"}],
                },
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

    assert context.version == "ade.manifest/v1.0"
    assert context.model is not None
