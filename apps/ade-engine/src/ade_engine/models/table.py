from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl


def _excel_column_letter(col: int) -> str:
    """Convert a 1-based column index to an Excel column label (1 -> A, 27 -> AA)."""
    if col < 1:
        raise ValueError("Excel columns are 1-based")

    letters: list[str] = []
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


@dataclass(frozen=True)
class TableRegion:
    """Openpyxl-friendly coordinates for a contiguous header+data block.

    Coordinates are 1-based and inclusive, matching Excel/openpyxl conventions.
    """

    header_row: int
    first_col: int
    last_row: int
    last_col: int
    header_inferred: bool = False

    def __post_init__(self) -> None:
        if self.header_row < 1:
            raise ValueError("header_row must be >= 1")
        if self.first_col < 1:
            raise ValueError("first_col must be >= 1")
        if self.last_row < self.header_row:
            raise ValueError("last_row must be >= header_row")
        if self.last_col < self.first_col:
            raise ValueError("last_col must be >= first_col")

    @property
    def data_first_row(self) -> int:
        return self.header_row + 1

    @property
    def has_data_rows(self) -> bool:
        return self.last_row >= self.data_first_row

    @property
    def data_row_count(self) -> int:
        return max(0, self.last_row - self.header_row)

    @property
    def col_count(self) -> int:
        return (self.last_col - self.first_col + 1) if self.last_col >= self.first_col else 0

    def _cell(self, row: int, col: int) -> str:
        return f"{_excel_column_letter(col)}{row}"

    @property
    def ref(self) -> str:
        """Range including header and all data rows (e.g., A1:D10)."""
        return f"{self._cell(self.header_row, self.first_col)}:{self._cell(self.last_row, self.last_col)}"

    @property
    def header_ref(self) -> str:
        """Header row only (e.g., A1:D1)."""
        return f"{self._cell(self.header_row, self.first_col)}:{self._cell(self.header_row, self.last_col)}"

    @property
    def data_ref(self) -> str | None:
        """Data rows only, excluding header (e.g., A2:D10)."""
        if not self.has_data_rows:
            return None
        return f"{self._cell(self.data_first_row, self.first_col)}:{self._cell(self.last_row, self.last_col)}"


@dataclass
class SourceColumn:
    index: int
    header: Any
    values: list[Any]


@dataclass
class MappedColumn:
    field_name: str
    source_index: int
    header: Any
    values: list[Any]
    score: float | None = None


@dataclass
class TableResult:
    """Processed table facts for reporting/debugging.

    Table values are stored only in ``table`` (a single Polars DataFrame).
    """

    sheet_name: str
    table: pl.DataFrame
    source_region: TableRegion
    source_columns: list[SourceColumn]
    table_index: int = 0
    sheet_index: int = 0
    mapped_columns: list[MappedColumn] = field(default_factory=list)
    unmapped_columns: list[SourceColumn] = field(default_factory=list)
    column_scores: dict[int, dict[str, float]] = field(default_factory=dict)
    duplicate_unmapped_indices: set[int] = field(default_factory=set)
    row_count: int = 0
    output_region: TableRegion | None = None
    output_sheet_name: str | None = None

    def mapping_lookup(self) -> dict[str, int | None]:
        return {col.field_name: col.source_index for col in self.mapped_columns}


__all__ = ["SourceColumn", "MappedColumn", "TableRegion", "TableResult"]
