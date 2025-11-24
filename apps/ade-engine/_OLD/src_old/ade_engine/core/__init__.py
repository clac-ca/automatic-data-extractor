"""Core engine data structures shared across modules."""

from .manifest import (
    ColumnMeta,
    ColumnSection,
    EngineDefaults,
    EngineSection,
    EngineWriter,
    HookCollection,
    ManifestContext,
    ManifestInfo,
    ManifestV1,
    ScriptRef,
)
from .models import EngineMetadata, JobContext, JobPaths, JobResult
from .phases import JobStatus, PipelinePhase
from .pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    FileExtraction,
    ScoreContribution,
    TableProcessingResult,
)

__all__ = [
    "ColumnMapping",
    "ColumnMeta",
    "ColumnModule",
    "ColumnSection",
    "EngineDefaults",
    "EngineMetadata",
    "EngineSection",
    "EngineWriter",
    "ExtraColumn",
    "FileExtraction",
    "HookCollection",
    "JobContext",
    "JobPaths",
    "JobResult",
    "JobStatus",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "PipelinePhase",
    "ScoreContribution",
    "ScriptRef",
    "TableProcessingResult",
]
