from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Sequence

import openpyxl
from pydantic import Field

from ade_api.common.schema import BaseSchema

DEFAULT_PREVIEW_ROWS = 200
DEFAULT_PREVIEW_COLUMNS = 50
MAX_PREVIEW_ROWS = 500
MAX_PREVIEW_COLUMNS = 200


class WorkbookSheetPreview(BaseSchema):
    """Table-ready preview for a single workbook sheet."""

    name: str
    headers: list[str]
    rows: list[list[str]]
    total_rows: int = Field(alias="totalRows")
    total_columns: int = Field(alias="totalColumns")
    truncated_rows: bool = Field(alias="truncatedRows")
    truncated_columns: bool = Field(alias="truncatedColumns")


class WorkbookPreview(BaseSchema):
    """Preview payload for a workbook."""

    sheets: list[WorkbookSheetPreview]


def build_workbook_preview_from_xlsx(
    path: Path,
    *,
    max_rows: int = DEFAULT_PREVIEW_ROWS,
    max_columns: int = DEFAULT_PREVIEW_COLUMNS,
    sheet_name: str | None = None,
    sheet_index: int | None = None,
) -> WorkbookPreview:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = _select_xlsx_sheets(workbook, sheet_name, sheet_index)
        previews = [
            _preview_xlsx_sheet(
                sheet,
                max_rows=max_rows,
                max_columns=max_columns,
            )
            for sheet in sheets
        ]
        return WorkbookPreview(sheets=previews)
    finally:
        workbook.close()


def build_workbook_preview_from_csv(
    path: Path,
    *,
    max_rows: int = DEFAULT_PREVIEW_ROWS,
    max_columns: int = DEFAULT_PREVIEW_COLUMNS,
    sheet_name: str | None = None,
    sheet_index: int | None = None,
) -> WorkbookPreview:
    name = path.stem or "Sheet1"
    if sheet_name and sheet_name != name:
        raise KeyError(f"Sheet {sheet_name!r} not found")
    if sheet_index not in (None, 0):
        raise IndexError("sheet_index out of range")

    rows: list[list[str]] = []
    total_rows = 0
    total_columns = 0

    with path.open("r", newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        for row in reader:
            total_rows += 1
            total_columns = max(total_columns, len(row))
            if len(rows) < max_rows:
                rows.append([_normalize_cell(cell) for cell in row])

    return WorkbookPreview(
        sheets=[
            _preview_sheet_from_rows(
                name=name,
                rows=rows,
                total_rows=total_rows,
                total_columns=total_columns,
                max_rows=max_rows,
                max_columns=max_columns,
            )
        ]
    )


def _select_xlsx_sheets(workbook, sheet_name: str | None, sheet_index: int | None):
    if sheet_name:
        if sheet_name not in workbook.sheetnames:
            raise KeyError(f"Sheet {sheet_name!r} not found")
        return [workbook[sheet_name]]
    if sheet_index is not None:
        if sheet_index < 0 or sheet_index >= len(workbook.sheetnames):
            raise IndexError("sheet_index out of range")
        return [workbook[workbook.sheetnames[sheet_index]]]
    return [workbook[name] for name in workbook.sheetnames]


def _preview_xlsx_sheet(sheet, *, max_rows: int, max_columns: int) -> WorkbookSheetPreview:
    rows: list[list[str]] = []
    for row in sheet.iter_rows(
        min_row=1,
        max_row=max_rows,
        max_col=max_columns,
        values_only=True,
    ):
        rows.append([_normalize_cell(cell) for cell in row])

    total_rows = sheet.max_row or 0
    total_columns = sheet.max_column or 0
    return _preview_sheet_from_rows(
        name=sheet.title,
        rows=rows,
        total_rows=total_rows,
        total_columns=total_columns,
        max_rows=max_rows,
        max_columns=max_columns,
    )


def _preview_sheet_from_rows(
    *,
    name: str,
    rows: Sequence[Sequence[str]],
    total_rows: int,
    total_columns: int,
    max_rows: int,
    max_columns: int,
) -> WorkbookSheetPreview:
    header_row = list(rows[0]) if rows else []
    preview_columns = max(
        1,
        min(
            max_columns,
            max(total_columns, len(header_row)),
        ),
    )
    headers = _build_headers(header_row, preview_columns)
    body_rows = [
        _normalize_row(list(row), len(headers)) for row in rows[1:]
    ]

    return WorkbookSheetPreview(
        name=name,
        headers=headers,
        rows=body_rows,
        total_rows=total_rows,
        total_columns=total_columns,
        truncated_rows=total_rows > max_rows,
        truncated_columns=total_columns > max_columns,
    )


def _normalize_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _normalize_row(row: Sequence[str], length: int) -> list[str]:
    return [row[index] if index < len(row) else "" for index in range(length)]


def _build_headers(raw: Sequence[str], total_columns: int) -> list[str]:
    trimmed = [cell.strip() for cell in raw]
    has_named = any(trimmed)
    header_count = max(total_columns, len(trimmed), 1)
    if has_named:
        headers = trimmed
    else:
        headers = [_column_label(index) for index in range(header_count)]
    return _normalize_row(headers, header_count)


def _column_label(index: int) -> str:
    label = ""
    position = index + 1
    while position > 0:
        remainder = (position - 1) % 26
        label = f"{chr(65 + remainder)}{label}"
        position = (position - 1) // 26
    return f"Column {label}"


__all__ = [
    "DEFAULT_PREVIEW_COLUMNS",
    "DEFAULT_PREVIEW_ROWS",
    "MAX_PREVIEW_COLUMNS",
    "MAX_PREVIEW_ROWS",
    "WorkbookPreview",
    "WorkbookSheetPreview",
    "build_workbook_preview_from_csv",
    "build_workbook_preview_from_xlsx",
]
