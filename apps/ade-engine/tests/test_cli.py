from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from subprocess import run

import pytest

from ade_engine import __version__
from fixtures.config_factories import make_minimal_config
from fixtures.sample_inputs import sample_csv


def _python_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}:{env.get('PYTHONPATH', '')}"
    return env


def test_cli_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)

    result = run(
        [sys.executable, "-m", "ade_engine", "version", "--manifest-path", str(config.manifest_path)],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["version"] == __version__
    assert payload["manifest_version"] == "1.0.0"


def test_cli_run_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)
    source = sample_csv(tmp_path)

    result = run(
        [
            sys.executable,
            "-m",
            "ade_engine",
            "run",
            "--input",
            str(source),
            "--manifest-path",
            str(config.manifest_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--logs-dir",
            str(tmp_path / "logs"),
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"
    assert Path(payload["logs_dir"]).exists()
    assert Path(payload["events_path"]).exists()
