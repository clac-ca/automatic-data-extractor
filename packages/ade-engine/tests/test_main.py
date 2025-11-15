from __future__ import annotations

import json
from pathlib import Path

from ade_engine.__main__ import main

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_ROOT = REPO_ROOT / "apps" / "api" / "app" / "templates" / "config_packages"
MANIFEST_PATH = TEMPLATES_ROOT / "default" / "src" / "ade_config" / "manifest.json"


def test_main_version_flag(capsys) -> None:
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "ade-engine" in captured.out


def test_main_prints_manifest(capsys) -> None:
    code = main(["--manifest-path", str(MANIFEST_PATH)])
    captured = capsys.readouterr()

    assert code == 0
    assert '"config_manifest"' in captured.out


def test_main_runs_job(tmp_path: Path, capsys) -> None:
    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "job-cli"
    input_dir = job_dir / "input"
    logs_dir = job_dir / "logs"
    input_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (input_dir / "data.csv").write_text("Member ID\n1\n", encoding="utf-8")

    manifest = {
        "schema_version": "ade.manifest@1",
        "script_api": 1,
        "engine": {
            "defaults": {"mapping_score_threshold": 0.0},
            "writer": {"append_unmapped_columns": False},
        },
        "columns": {
            "order": ["member_id"],
            "meta": {"member_id": {"label": "Member ID"}},
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

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
