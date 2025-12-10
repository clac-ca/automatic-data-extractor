from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class SourceColumn:
    index: int
    header: Any
    values: List[Any]


@dataclass
class MappedColumn:
    field_name: str
    source_index: int
    header: Any
    values: List[Any]
    score: float | None = None


@dataclass
class TableData:
    sheet_name: str
    header_row_index: int
    source_columns: List[SourceColumn]
    mapped_columns: List[MappedColumn] = field(default_factory=list)
    unmapped_columns: List[SourceColumn] = field(default_factory=list)
    rows: List[dict[str, Any]] = field(default_factory=list)  # normalized rows
    issues: List[dict[str, Any]] = field(default_factory=list)

    def mapping_lookup(self) -> dict[str, int]:
        return {col.field_name: col.source_index for col in self.mapped_columns}


__all__ = ["SourceColumn", "MappedColumn", "TableData"]
