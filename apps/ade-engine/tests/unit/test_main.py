from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.cli.common import collect_input_files
from ade_engine.settings import Settings


def test_collect_input_files_includes_supported_nested_inputs(tmp_path):
    input_dir = tmp_path / "inputs"
    nested = input_dir / "nested"
    nested.mkdir(parents=True)

    supported = nested / "file.xlsx"
    supported.write_text("data")
    (nested / "ignore.txt").write_text("skip")

    collected = collect_input_files(
        input_dir=input_dir,
        include=[],
        exclude=[],
        explicit_inputs=[],
        settings=Settings(),
    )

    assert collected == [supported]


def test_collect_input_files_allows_user_include_globs(tmp_path):
    input_dir = tmp_path / "inputs"
    reports = input_dir / "reports"
    reports.mkdir(parents=True)

    excel = reports / "report.xlsm"
    excel.write_text("data")
    notes = reports / "notes.txt"
    notes.write_text("extra")

    collected = collect_input_files(
        input_dir=input_dir,
        include=["*.xlsm"],
        exclude=[],
        explicit_inputs=[],
        settings=Settings(),
    )

    assert collected == [excel]


def test_collect_input_files_excludes_recursively(tmp_path):
    input_dir = tmp_path / "inputs"
    nested = input_dir / "nested"
    nested.mkdir(parents=True)

    keep = nested / "keep.xlsx"
    keep.write_text("data")
    drop = nested / "data_raw.csv"
    drop.write_text("skip")

    collected = collect_input_files(
        input_dir=input_dir,
        include=[],
        exclude=["*_raw.*"],
        explicit_inputs=[],
        settings=Settings(),
    )

    assert collected == [keep]
