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
    frames = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert frames, "Expected NDJSON engine events on stdout"
    complete = frames[-1]
    assert complete["type"] == "engine.complete"
    assert complete["payload"]["status"] == "succeeded"
    assert (tmp_path / "logs").exists()
    run_log_files = list((tmp_path / "logs").glob("engine_events.ndjson"))
    assert len(run_log_files) == 1
    assert run_log_files[0].stat().st_size > 0
    run_output_files = list((tmp_path / "out").glob("normalized.xlsx"))
    assert len(run_output_files) == 1


def test_cli_run_with_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_root = tmp_path / "config_root"
    config_root.mkdir()
    config = make_minimal_config(config_root, monkeypatch)
    source = sample_csv(tmp_path)

    result = run(
        [
            sys.executable,
            "-m",
            "ade_engine",
            "run",
            "--input",
            str(source),
            "--config-package",
            str(config_root),
            "--output-dir",
            str(source.parent / "output"),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )

    assert result.returncode == 0
    frames = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert frames, "Expected NDJSON engine events on stdout"
    complete = frames[-1]
    assert complete["type"] == "engine.complete"
    assert complete["payload"]["status"] == "succeeded"
    assert (source.parent / "output").exists()
    log_files = list((source.parent / "output").glob("engine_events.ndjson"))
    assert log_files == []
    output_files = list((source.parent / "output").glob("normalized.xlsx"))
    assert len(output_files) == 1


def test_cli_run_multiple_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)
    source_a = sample_csv(tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    source_b = sample_csv(other_dir)

    result = run(
        [
            sys.executable,
            "-m",
            "ade_engine",
            "run",
            "--input",
            str(source_a),
            "--input",
            str(source_b),
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    frames = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    complete_events = [frame for frame in frames if frame.get("type") == "engine.complete"]
    assert len(complete_events) == 2

    out_files = [
        tmp_path / "output" / "normalized.xlsx",
        other_dir / "output" / "normalized.xlsx",
    ]
    for path in out_files:
        assert path.exists()
