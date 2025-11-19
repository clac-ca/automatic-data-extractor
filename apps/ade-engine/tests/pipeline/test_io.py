from pathlib import Path

import openpyxl

from ade_engine.pipeline.io import list_input_files, read_table, sheet_name


def test_list_input_files_filters_extensions(tmp_path: Path) -> None:
    files = [
        tmp_path / "data.csv",
        tmp_path / "notes.txt",
        tmp_path / "table.xlsx",
    ]
    (tmp_path / "dir").mkdir()
    for path in files:
        if path.suffix == ".xlsx":
            workbook = openpyxl.Workbook()
            workbook.save(path)
            workbook.close()
        else:
            path.write_text("header\nvalue\n", encoding="utf-8")
    results = list_input_files(tmp_path)
    assert [file.name for file in results] == ["data.csv", "table.xlsx"]


def test_read_table_handles_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "values.csv"
    csv_path.write_text("Name,Email\nAlice,alice@example.com\n", encoding="utf-8")
    header, rows = read_table(csv_path)
    assert header == ["Name", "Email"]
    assert rows[0][1] == "alice@example.com"


def test_sheet_name_sanitizes_input() -> None:
    assert sheet_name("Employee-List 2024") == "Employee List 2024"
