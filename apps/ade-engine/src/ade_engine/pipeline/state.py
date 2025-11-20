"""Finite-state machine coordinating pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from ..logging import StructuredLogger
from ..model import JobContext, JobResult


class PipelinePhase(str, Enum):
    """Recognized pipeline phases."""

    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    BEFORE_SAVE = "before_save"
    WRITING_OUTPUT = "writing_output"
    COMPLETED = "completed"
    FAILED = "failed"


_TRANSITIONS: dict[PipelinePhase, tuple[PipelinePhase, ...]] = {
    PipelinePhase.INITIALIZED: (PipelinePhase.EXTRACTING, PipelinePhase.FAILED),
    PipelinePhase.EXTRACTING: (PipelinePhase.BEFORE_SAVE, PipelinePhase.FAILED),
    PipelinePhase.BEFORE_SAVE: (PipelinePhase.WRITING_OUTPUT, PipelinePhase.FAILED),
    PipelinePhase.WRITING_OUTPUT: (PipelinePhase.COMPLETED, PipelinePhase.FAILED),
    PipelinePhase.COMPLETED: (),
    PipelinePhase.FAILED: (),
}


@dataclass(slots=True)
class PipelineStateMachine:
    """Stateful orchestrator for the ADE job pipeline."""

    job: JobContext
    logger: StructuredLogger
    phase: PipelinePhase = PipelinePhase.INITIALIZED
    tables: list = field(default_factory=list)
    output_paths: tuple[Path, ...] = ()

    def transition(self, next_phase: PipelinePhase, **payload) -> None:
        if next_phase not in _TRANSITIONS[self.phase]:
            raise RuntimeError(
                f"Invalid pipeline transition from {self.phase.value} to {next_phase.value}"
            )
        self.phase = next_phase
        self.logger.transition(next_phase.value, **payload)

    def execute(
        self,
        *,
        extractor: Callable[[], list],
        after_extract: Callable[[Iterable], None],
        before_save: Callable[[Iterable], None],
        writer: Callable[[Iterable], Path],
    ) -> None:
        try:
            self._run_extraction(extractor, after_extract)
            self._run_before_save(before_save)
            output = self._run_writer(writer)
            self.transition(PipelinePhase.COMPLETED, outputs=[str(path) for path in output])
            self.output_paths = output
        except Exception as exc:
            self.phase = PipelinePhase.FAILED
            self.logger.transition(PipelinePhase.FAILED.value, error=str(exc))
            raise

    def _run_extraction(
        self, extractor: Callable[[], list], after_extract: Callable[[Iterable], None]
    ) -> None:
        self.transition(PipelinePhase.EXTRACTING)
        tables = extractor()
        self.tables = list(tables)
        after_extract(self.tables)

    def _run_before_save(self, before_save: Callable[[Iterable], None]) -> None:
        self.transition(PipelinePhase.BEFORE_SAVE, table_count=len(self.tables))
        before_save(self.tables)

    def _run_writer(self, writer: Callable[[Iterable], Path]) -> tuple[Path, ...]:
        self.transition(PipelinePhase.WRITING_OUTPUT, table_count=len(self.tables))
        path = writer(self.tables)
        if isinstance(path, Path):
            return (path,)
        if isinstance(path, tuple):
            return path
        if isinstance(path, list):
            return tuple(path)
        raise TypeError("Writer must return a Path or iterable of Paths")


def build_result(state: PipelineStateMachine, error: str | None = None) -> JobResult:
    """Assemble a :class:`JobResult` from the state machine's state."""

    status = "failed" if error or state.phase is PipelinePhase.FAILED else "succeeded"
    processed = tuple(getattr(table, "source_name", "") for table in state.tables)
    return JobResult(
        job_id=state.job.job_id,
        status=status,
        artifact_path=state.job.paths.artifact_path,
        events_path=state.job.paths.events_path,
        output_paths=state.output_paths,
        processed_files=processed,
        error=error,
    )


__all__ = ["PipelinePhase", "PipelineStateMachine", "build_result"]
