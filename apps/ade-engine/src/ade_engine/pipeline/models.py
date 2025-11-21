"""Compatibility re-exports for pipeline dataclasses."""

from ade_engine.core.pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    FileExtraction,
    ScoreContribution,
)

__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
]
