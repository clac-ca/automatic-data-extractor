"""Lightweight context objects passed to hooks and pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.types.origin import TableOrigin, TableRegion


@dataclass
class RunContext:
    """Run-scoped context shared across pipeline stages."""

    source_path: Path
    output_path: Path
    source_workbook: openpyxl.Workbook
    output_workbook: openpyxl.Workbook
    state: dict[str, Any] = field(default_factory=dict)
    logger: Any | None = None


@dataclass
class WorksheetContext:
    run: RunContext
    sheet_index: int
    source_worksheet: Worksheet
    output_worksheet: Worksheet


@dataclass
class TableContext:
    """Table-scoped context (single detected table within a worksheet)."""

    sheet: WorksheetContext
    origin: TableOrigin
    region: TableRegion
    header_row_index: int
    columns: list[Any] = field(default_factory=list)  # populated with mapped columns
    unmapped_columns: list[Any] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)  # normalized rows
    placement: Any | None = None
    mapping_patch: Any | None = None


__all__ = ["RunContext", "WorksheetContext", "TableContext"]
