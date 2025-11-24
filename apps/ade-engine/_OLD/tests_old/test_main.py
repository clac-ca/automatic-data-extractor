from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from ade_engine.__main__ import main


def test_main_version_flag(capsys) -> None:
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "ade-engine" in captured.out


def test_main_prints_manifest(tmp_path: Path, capsys) -> None:
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

    code = main(["--manifest-path", str(manifest_path)])
    captured = capsys.readouterr()

    assert code == 0
    assert '"config_manifest"' in captured.out


def _build_config_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_root = tmp_path / "cfg"
    config_pkg = pkg_root / "ade_config"
    columns_dir = config_pkg / "columns"
    columns_dir.mkdir(parents=True)
    (config_pkg / "__init__.py").write_text("", encoding="utf-8")
    (columns_dir / "__init__.py").write_text("", encoding="utf-8")

    member_module = textwrap.dedent(
        """
        def detect_from_header(**kwargs):
            header = kwargs.get("header") or ""
            if header.lower() == "member id":
                return {"scores": {kwargs["field_name"]: 1.0}}
            return {"scores": {}}
        """
    )
    (columns_dir / "member_id.py").write_text(member_module, encoding="utf-8")

    manifest = {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": "Test Config",
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {"mapping_score_threshold": 0.0, "detector_sample_size": 4},
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": False,
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
        "env": {},
    }

    manifest_path = config_pkg / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.syspath_prepend(str(pkg_root))
    for name in list(sys.modules):
        if name == "ade_config" or name.startswith("ade_config."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    return manifest_path


def test_main_runs_job(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-cli"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (input_dir / "data.csv").write_text("Member ID\n1\n", encoding="utf-8")

    manifest_path = _build_config_package(tmp_path, monkeypatch)

    code = main(
        [
            "--job-id",
            "job-cli",
            "--jobs-dir",
            str(jobs_dir),
            "--manifest-path",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert '"status": "succeeded"' in captured.out
