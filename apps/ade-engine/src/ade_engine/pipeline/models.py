"""Data models shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence

from ade_engine.schemas.manifest import ColumnMeta


@dataclass(slots=True)
class ScoreContribution:
    """Record how a detector influenced a field's final score."""

    field: str
    detector: str
    delta: float


@dataclass(slots=True)
class ColumnMapping:
    """Link a manifest field to a concrete input column."""

    field: str
    header: str
    index: int
    score: float
    contributions: tuple[ScoreContribution, ...]


@dataclass(slots=True)
class ExtraColumn:
    """Preserve unmapped columns in the normalized output."""

    header: str
    index: int
    output_header: str


@dataclass(slots=True)
class FileExtraction:
    """Normalized table data pulled from a single input file."""

    source_name: str
    sheet_name: str
    mapped_columns: list[ColumnMapping]
    extra_columns: list[ExtraColumn]
    rows: list[list[Any]]
    header_row: list[str]
    validation_issues: list[dict[str, Any]]


@dataclass(slots=True)
class ColumnModule:
    """Manifest-backed module that contributes detectors/transforms/validators."""

    field: str
    meta: Mapping[str, Any]
    definition: ColumnMeta
    module: ModuleType
    detectors: tuple[Callable[..., Mapping[str, Any]], ...]
    transformer: Callable[..., Mapping[str, Any] | None] | None
    validator: Callable[..., Sequence[Mapping[str, Any]]] | None


__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
]
