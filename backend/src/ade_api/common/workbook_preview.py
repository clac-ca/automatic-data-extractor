from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import openpyxl
from pydantic import Field

from ade_api.common.schema import BaseSchema

DEFAULT_PREVIEW_ROWS = 10_000
DEFAULT_PREVIEW_COLUMNS = 10_000
MAX_PREVIEW_ROWS = 10_000
MAX_PREVIEW_COLUMNS = 10_000


class WorkbookSheetPreview(BaseSchema):
    """Preview for a single workbook sheet."""

    name: str
    index: int = Field(ge=0)
    rows: list[list[str]]
    total_rows: int = Field(alias="totalRows")
    total_columns: int = Field(alias="totalColumns")
    truncated_rows: bool = Field(alias="truncatedRows")
    truncated_columns: bool = Field(alias="truncatedColumns")


def build_workbook_preview_from_xlsx(
    path: Path,
    *,
    max_rows: int = DEFAULT_PREVIEW_ROWS,
    max_columns: int = DEFAULT_PREVIEW_COLUMNS,
    trim_empty_columns: bool = False,
    trim_empty_rows: bool = False,
    sheet_name: str | None = None,
    sheet_index: int | None = None,
) -> WorkbookSheetPreview:
    with path.open("rb") as handle:
        workbook = openpyxl.load_workbook(
            handle,
            read_only=True,
            data_only=True,
            keep_links=False,
        )
        try:
            index, sheet = _select_xlsx_sheet(workbook, sheet_name, sheet_index)
            return _preview_xlsx_sheet(
                sheet,
                index=index,
                max_rows=max_rows,
                max_columns=max_columns,
                trim_empty_columns=trim_empty_columns,
                trim_empty_rows=trim_empty_rows,
            )
        finally:
            workbook.close()


def build_workbook_preview_from_csv(
    path: Path,
    *,
    max_rows: int = DEFAULT_PREVIEW_ROWS,
    max_columns: int = DEFAULT_PREVIEW_COLUMNS,
    trim_empty_columns: bool = False,
    trim_empty_rows: bool = False,
    sheet_name: str | None = None,
    sheet_index: int | None = None,
) -> WorkbookSheetPreview:
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

    return _preview_sheet_from_rows(
        name=name,
        index=0,
        rows=rows,
        total_rows=total_rows,
        total_columns=total_columns,
        max_rows=max_rows,
        max_columns=max_columns,
        trim_empty_columns=trim_empty_columns,
        trim_empty_rows=trim_empty_rows,
    )


def _select_xlsx_sheet(workbook, sheet_name: str | None, sheet_index: int | None):
    if sheet_name:
        if sheet_name not in workbook.sheetnames:
            raise KeyError(f"Sheet {sheet_name!r} not found")
        index = workbook.sheetnames.index(sheet_name)
        return index, workbook[sheet_name]
    effective_index = sheet_index if sheet_index is not None else 0
    if effective_index < 0 or effective_index >= len(workbook.sheetnames):
        raise IndexError("sheet_index out of range")
    return effective_index, workbook[workbook.sheetnames[effective_index]]


def _preview_xlsx_sheet(
    sheet,
    *,
    index: int,
    max_rows: int,
    max_columns: int,
    trim_empty_columns: bool,
    trim_empty_rows: bool,
) -> WorkbookSheetPreview:
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
        index=index,
        rows=rows,
        total_rows=total_rows,
        total_columns=total_columns,
        max_rows=max_rows,
        max_columns=max_columns,
        trim_empty_columns=trim_empty_columns,
        trim_empty_rows=trim_empty_rows,
    )


def _preview_sheet_from_rows(
    *,
    name: str,
    index: int,
    rows: Sequence[Sequence[str]],
    total_rows: int,
    total_columns: int,
    max_rows: int,
    max_columns: int,
    trim_empty_columns: bool,
    trim_empty_rows: bool,
) -> WorkbookSheetPreview:
    max_row_length = max((len(row) for row in rows), default=0)
    preview_columns = min(max_columns, total_columns or max_row_length)
    normalized_rows = [_normalize_row(list(row), preview_columns) for row in rows]
    if trim_empty_rows:
        normalized_rows = _trim_empty_rows(normalized_rows)
    if trim_empty_columns:
        normalized_rows = _trim_empty_columns(normalized_rows)

    return WorkbookSheetPreview(
        name=name,
        index=index,
        rows=normalized_rows,
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


def _trim_empty_columns(rows: Sequence[Sequence[str]]) -> list[list[str]]:
    if not rows:
        return [list(row) for row in rows]

    column_count = max((len(row) for row in rows), default=0)
    if column_count == 0:
        return [list(row) for row in rows]

    keep_indices = [
        index for index in range(column_count) if any(row[index].strip() for row in rows)
    ]

    if not keep_indices:
        return [[] for _ in rows]

    return [[row[index] for index in keep_indices] for row in rows]


def _trim_empty_rows(rows: Sequence[Sequence[str]]) -> list[list[str]]:
    return [list(row) for row in rows if any(cell.strip() for cell in row)]


__all__ = [
    "DEFAULT_PREVIEW_COLUMNS",
    "DEFAULT_PREVIEW_ROWS",
    "MAX_PREVIEW_COLUMNS",
    "MAX_PREVIEW_ROWS",
    "WorkbookSheetPreview",
    "build_workbook_preview_from_csv",
    "build_workbook_preview_from_xlsx",
]
