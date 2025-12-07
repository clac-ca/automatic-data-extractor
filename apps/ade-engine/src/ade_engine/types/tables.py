"""Table stage models used throughout the engine pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ade_engine.types.issues import ValidationIssue
from ade_engine.types.origin import TableOrigin, TableRegion


@dataclass(frozen=True)
class ExtractedTable:
    """Raw header and rows extracted from a detected region."""

    origin: TableOrigin
    region: TableRegion
    header: list[str]
    rows: list[list[Any]]

    def preview(self, n: int = 10) -> list[list[Any]]:
        """Return the first ``n`` data rows for quick inspection."""
        return self.rows[:n]


@dataclass(frozen=True)
class MappedField:
    """Canonical field mapping produced by column detectors."""

    field: str
    source_col: int | None  # 0-based index within the extracted region
    source_header: str | None
    score: float | None


@dataclass(frozen=True)
class PassthroughField:
    """Unmapped/preserved source column."""

    source_col: int
    source_header: str
    output_name: str


@dataclass(frozen=True)
class ColumnMapping:
    """Mapping result describing canonical + passthrough columns."""

    fields: list[MappedField]
    passthrough: list[PassthroughField]

    @property
    def output_header(self) -> list[str]:
        return [field.field for field in self.fields] + [p.output_name for p in self.passthrough]


@dataclass(frozen=True)
class MappedTable:
    """Logical projection of extracted rows onto canonical order."""

    origin: TableOrigin
    region: TableRegion
    mapping: ColumnMapping
    extracted: ExtractedTable
    header: list[str]
    rows: Sequence[Sequence[Any]]


@dataclass
class NormalizedTable:
    """Cleaned rows ready for output, plus validation issues."""

    origin: TableOrigin
    region: TableRegion
    header: list[str]
    rows: list[list[Any]]
    issues: list[ValidationIssue]


__all__ = [
    "ExtractedTable",
    "MappedField",
    "PassthroughField",
    "ColumnMapping",
    "MappedTable",
    "NormalizedTable",
]
