from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.engine import Engine
from ade_engine.settings import Settings
from ade_engine.types.run import RunRequest, RunStatus


def _write_config_package(root: Path) -> None:
    pkg = root / "ade_config"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    (pkg / "rows.py").write_text(
        """
from ade_engine.registry import row_detector, RowKind

@row_detector(row_kind=RowKind.HEADER, priority=10)
def pick_header(ctx):
    return {"header": 1.0}
""",
        encoding="utf-8",
    )

    (pkg / "columns.py").write_text(
        """
from ade_engine.registry import column_detector, column_transform, column_validator

@column_detector(field="email", priority=20)
def detect_email(ctx):
    header = (ctx.header or "").strip().lower()
    return 1.0 if header == "email" else 0.0

@column_detector(field="name", priority=10)
def detect_name(ctx):
    header = (ctx.header or "").strip().lower()
    return 1.0 if header == "name" else 0.0

@column_transform(field="email")
def normalize_email(ctx):
    return [str(v).lower() if v is not None else None for v in ctx.values]

@column_validator(field="email")
def validate_email(ctx):
    issues = []
    for idx, v in enumerate(ctx.values):
        if v and "@" not in str(v):
            issues.append({"passed": False, "row_index": idx, "message": "invalid email", "value": v})
    return issues or {"passed": True}
""",
        encoding="utf-8",
    )


def _write_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Email", "Name", "Notes"])
    ws.append(["USER@Example.com", "Alice", "note-1"])
    ws.append(["bademail", "Bob", "note-2"])
    wb.save(path)


def test_end_to_end_pipeline(tmp_path: Path):
    config_root = tmp_path / "cfg"
    config_root.mkdir()
    _write_config_package(config_root)

    source = tmp_path / "input.xlsx"
    _write_workbook(source)

    engine = Engine(settings=Settings())
    output_dir = tmp_path / "out"
    logs_dir = tmp_path / "logs"
    req = RunRequest(
        config_package=config_root,
        input_file=source,
        output_dir=output_dir,
        logs_dir=logs_dir,
    )

    result = engine.run(req)
    assert result.status == RunStatus.SUCCEEDED
    output_file = output_dir / f"{source.stem}_normalized.xlsx"
    assert output_file.exists()

    wb = openpyxl.load_workbook(output_file)
    ws = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))[0:3]]
    assert headers == ["email", "name", "raw_Notes"]

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert rows[0][0] == "user@example.com"
    assert rows[0][1] == "Alice"
    assert rows[0][2] == "note-1"
    assert rows[1][0] == "bademail"  # unchanged but still present
    assert rows[1][2] == "note-2"

    wb.close()
