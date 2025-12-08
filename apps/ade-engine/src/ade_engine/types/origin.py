"""Origin and placement types for workbook tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl.worksheet.cell_range import CellRange
from openpyxl.worksheet.worksheet import Worksheet


@dataclass(frozen=True)
class TableOrigin:
    """Stable identifier for a detected table within a workbook."""

    source_path: Path
    sheet_name: str
    sheet_index: int  # 0-based
    table_index: int  # 0-based within the sheet


@dataclass(frozen=True)
class TableRegion:
    """Bounding box for a detected table in source worksheet coordinates."""

    min_row: int
    max_row: int
    min_col: int
    max_col: int


@dataclass(frozen=True)
class TablePlacement:
    """Where a normalized table was written in the output workbook."""

    worksheet: Worksheet
    cell_range: CellRange
    origin: TableOrigin


__all__ = ["TableOrigin", "TableRegion", "TablePlacement"]
