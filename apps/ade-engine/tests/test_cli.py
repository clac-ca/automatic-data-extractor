from __future__ import annotations

import json
import os
import sys
from typing import Any
from pathlib import Path
from subprocess import run

import pytest

from ade_engine import __version__
from fixtures.config_factories import make_minimal_config
from fixtures.sample_inputs import sample_csv


def _json_frames(stdout: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            frames.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return frames


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
    frames = _json_frames(result.stdout)
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
    frames = _json_frames(result.stdout)
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
    frames = _json_frames(result.stdout)
    complete_events = [frame for frame in frames if frame.get("type") == "engine.complete"]
    assert len(complete_events) == 2

    out_files = [
        tmp_path / "output" / "normalized.xlsx",
        other_dir / "output" / "normalized.xlsx",
    ]
    for path in out_files:
        assert path.exists()


def test_cli_run_quiet_suppresses_ndjson(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            "--quiet",
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    frames = _json_frames(result.stdout)
    assert frames == []  # NDJSON suppressed
    assert (tmp_path / "logs" / "engine_events.ndjson").exists()
    assert (tmp_path / "out" / "normalized.xlsx").exists()


def test_cli_run_format_json_outputs_single_objects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    payloads = _json_frames(result.stdout)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["status"] == "succeeded"
    assert payload["fields_mapped_count"] == 2
    assert Path(payload["output_file"]).exists()


def test_cli_run_aggregate_summary_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            "--quiet",
            "--aggregate-summary",
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    assert "Aggregate: runs=2" in result.stdout
    assert "Field frequency:" in result.stdout


def test_cli_run_aggregate_summary_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)
    source_a = sample_csv(tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    source_b = sample_csv(other_dir)
    aggregate_path = tmp_path / "aggregate.json"

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
            "--format",
            "json",
            "--quiet",
            "--aggregate-summary",
            "--aggregate-summary-file",
            str(aggregate_path),
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    stdout_payloads = _json_frames(result.stdout)
    assert len(stdout_payloads) == 1
    aggregate = stdout_payloads[0]
    assert aggregate["totals"]["runs"] == 2
    assert aggregate["totals"]["failed"] == 0
    assert aggregate["field_frequency"]["member_id"] == 2
    assert aggregate_path.exists()
    saved = json.loads(aggregate_path.read_text())
    assert saved["totals"]["runs"] == 2
    assert len(saved["runs"]) == 2


def test_cli_input_dir_include_exclude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    included = sample_csv(input_root)
    excluded_dir = input_root / "skip"
    excluded_dir.mkdir()
    (excluded_dir / "skip.csv").write_text("member_id,value\n1,1\n")
    explicit_dir = tmp_path / "explicit"
    explicit_dir.mkdir()
    explicit = sample_csv(explicit_dir)

    result = run(
        [
            sys.executable,
            "-m",
            "ade_engine",
            "run",
            "--input-dir",
            str(input_root),
            "--include",
            "*.csv",
            "--exclude",
            "skip/*",
            "--input",
            str(explicit),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        env=_python_env(tmp_path),
    )

    assert result.returncode == 0
    frames = _json_frames(result.stdout)
    complete_events = [frame for frame in frames if frame.get("type") == "engine.complete"]
    assert len(complete_events) == 2
    assert (tmp_path / "out" / included.stem / "normalized.xlsx").exists()
    assert (tmp_path / "out" / explicit.stem / "normalized.xlsx").exists()
    assert not (tmp_path / "out" / "skip" / "normalized.xlsx").exists()
