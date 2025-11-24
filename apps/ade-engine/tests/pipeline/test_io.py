from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from ade_engine.core.errors import InputError
from ade_engine.infra.io import iter_csv_rows, iter_sheet_rows, list_input_files


def test_list_input_files_filters_hidden_and_sorts(tmp_path: Path) -> None:
    csv_path = tmp_path / "b.csv"
    csv_path.write_text("1,2\n", encoding="utf-8")

    xlsx_path = tmp_path / "a.xlsx"
    xlsx_path.write_text("", encoding="utf-8")

    (tmp_path / ".ignore.csv").write_text("", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "inner.csv").write_text("", encoding="utf-8")

    discovered = list_input_files(tmp_path)

    assert discovered == sorted([xlsx_path.resolve(), csv_path.resolve()])


def test_list_input_files_raises_on_unsupported_extension(tmp_path: Path) -> None:
    (tmp_path / "valid.csv").write_text("", encoding="utf-8")
    (tmp_path / "bad.xls").write_text("", encoding="utf-8")

    with pytest.raises(InputError):
        list_input_files(tmp_path)


def test_iter_csv_rows_handles_bom_and_row_indices(tmp_path: Path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("\ufeffh1,h2\nv1,v2\n", encoding="utf-8")

    rows = list(iter_csv_rows(csv_path))

    assert rows == [(1, ["h1", "h2"]), (2, ["v1", "v2"])]


def test_iter_csv_rows_rejects_missing_or_wrong_type(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    with pytest.raises(InputError):
        list(iter_csv_rows(missing))

    wrong_type = tmp_path / "not_excel.txt"
    wrong_type.write_text("", encoding="utf-8")
    with pytest.raises(InputError):
        list(iter_csv_rows(wrong_type))


def test_iter_sheet_rows_streams_values(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workbook.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["header", None])
    sheet.append([1, 2.5])
    sheet.append([True, datetime(2024, 1, 1)])
    workbook.save(workbook_path)
    workbook.close()

    rows = list(iter_sheet_rows(workbook_path, "Data"))

    assert rows[0] == (1, ["header", None])
    assert rows[1] == (2, [1, 2.5])
    assert rows[2] == (3, [True, datetime(2024, 1, 1)])


def test_iter_sheet_rows_validates_sheet_names(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workbook.xlsx"
    workbook = Workbook()
    workbook.save(workbook_path)
    workbook.close()

    with pytest.raises(InputError):
        list(iter_sheet_rows(workbook_path, "Missing"))

    with pytest.raises(InputError):
        list(iter_sheet_rows(workbook_path.with_suffix(".csv"), "Data"))
