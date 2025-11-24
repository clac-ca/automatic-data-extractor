"""Composable pipeline runner for extract/write stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import FileExtraction
from ade_engine.core.phases import PipelinePhase
from ade_engine.telemetry.logging import PipelineLogger


@dataclass(slots=True)
class PipelineRunner:
    """Coordinate pipeline phases while recording transitions."""

    job: JobContext
    logger: PipelineLogger
    phase: PipelinePhase = PipelinePhase.INITIALIZED
    tables: list[FileExtraction] = field(default_factory=list)
    output_paths: tuple[Path, ...] = ()

    def run(
        self,
        *,
        extract_stage: Callable[[JobContext, Any, PipelineLogger], list[FileExtraction]],
        write_stage: Callable[[JobContext, list[FileExtraction], PipelineLogger], Path | Sequence[Path]],
    ) -> None:
        """Execute extract then write, advancing phases and emitting transitions."""

        try:
            self._transition(PipelinePhase.EXTRACTING)
            self.tables = list(extract_stage(self.job, None, self.logger))

            self._transition(
                PipelinePhase.WRITING_OUTPUT, table_count=len(self.tables)
            )
            output = write_stage(self.job, self.tables, self.logger)
            self.output_paths = self._normalize_output_paths(output)

            self._transition(
                PipelinePhase.COMPLETED,
                outputs=[str(path) for path in self.output_paths],
            )
        except Exception as exc:  # pragma: no cover - will be exercised in integration
            self.phase = PipelinePhase.FAILED
            self.logger.transition(PipelinePhase.FAILED.value, error=str(exc))
            raise

    def _transition(self, next_phase: PipelinePhase, **payload: Any) -> None:
        self.phase = next_phase
        self.logger.transition(next_phase.value, **payload)

    def _normalize_output_paths(self, value: Path | Sequence[Path]) -> tuple[Path, ...]:
        if isinstance(value, Path):
            return (value,)
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise TypeError("Writer must return a Path or iterable of Paths")


__all__ = ["PipelineRunner"]
