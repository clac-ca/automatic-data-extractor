from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl


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


@dataclass(frozen=True)
class TableRegionInfo:
    """0-based source row bounds for a detected table region."""

    header_row_index: int
    data_start_row_index: int
    data_end_row_index: int
    header_inferred: bool = False


@dataclass
class TableResult:
    """Processed table facts for reporting/debugging.

    Table values are stored only in ``table`` (a single Polars DataFrame).
    """

    sheet_name: str
    table: pl.DataFrame
    header_row_index: int
    source_columns: list[SourceColumn]
    table_index: int = 0
    sheet_index: int = 0
    region: TableRegionInfo | None = None
    mapped_columns: list[MappedColumn] = field(default_factory=list)
    unmapped_columns: list[SourceColumn] = field(default_factory=list)
    column_scores: dict[int, dict[str, float]] = field(default_factory=dict)
    duplicate_unmapped_indices: set[int] = field(default_factory=set)
    row_count: int = 0
    output_range: str | None = None
    output_sheet_name: str | None = None

    def mapping_lookup(self) -> dict[str, int | None]:
        return {col.field_name: col.source_index for col in self.mapped_columns}


__all__ = ["SourceColumn", "MappedColumn", "TableRegionInfo", "TableResult"]
