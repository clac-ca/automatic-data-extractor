from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterable, Protocol

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import NormalizedTable, RunContext, RunError, RunPaths, RunStatus
from ade_engine.schemas.artifact import (
    ArtifactError,
    ArtifactNote,
    ArtifactV1,
    ConfigArtifact,
    MappedColumn as ArtifactMappedColumn,
    RunArtifact,
    ScoreContribution,
    TableArtifact,
    TableHeader,
    UnmappedColumn as ArtifactUnmappedColumn,
    ValidationIssue as ArtifactValidationIssue,
)


class ArtifactSink(Protocol):
    """Lifecycle hooks for building the artifact JSON output."""

    def start(self, run: RunContext, manifest: ManifestContext) -> None: ...

    def record_table(self, table: NormalizedTable) -> None: ...

    def note(self, message: str, *, level: str = "info", details: dict | None = None) -> None: ...

    def mark_success(self, outputs: Iterable[Path]) -> None: ...

    def mark_failure(self, error: RunError, *, details: dict | None = None) -> None: ...

    def flush(self) -> None: ...


def _format_timestamp(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _relative_paths(paths: Iterable[Path], base: Path | None) -> list[str]:
    results: list[str] = []
    for path in paths:
        try:
            if base:
                results.append(str(path.relative_to(base)))
                continue
        except ValueError:
            pass
        results.append(str(path))
    return results


@dataclass
class FileArtifactSink:
    """Concrete artifact sink that writes `artifact.json` atomically."""

    artifact_path: Path
    _artifact: ArtifactV1 | None = None
    _paths: RunPaths | None = None
    _run: RunContext | None = None

    def start(self, run: RunContext, manifest: ManifestContext) -> None:
        self._paths = run.paths
        self._run = run
        run_started = _format_timestamp(run.started_at)
        try:
            engine_version = version("ade-engine")
        except PackageNotFoundError:
            engine_version = manifest.model.version
        self._artifact = ArtifactV1(
            run=RunArtifact(
                id=run.run_id,
                status=RunStatus.RUNNING,
                started_at=run_started or "",
                engine_version=engine_version,
            ),
            config=ConfigArtifact(
                schema_id=manifest.model.schema_id,
                version=manifest.model.version,
                name=manifest.model.name,
            ),
            tables=[],
            notes=[],
        )

    def record_table(self, table: NormalizedTable) -> None:
        if not self._artifact:
            msg = "ArtifactSink.start must be called before recording tables."
            raise RuntimeError(msg)

        extracted = table.mapped.extracted
        mapped_columns = [
            ArtifactMappedColumn(
                field=column.field,
                header=column.header,
                source_column_index=column.source_column_index,
                score=column.score,
                contributions=[
                    ScoreContribution(detector=contrib.detector, delta=contrib.delta)
                    for contrib in column.contributions
                ],
            )
            for column in table.mapped.column_map.mapped_columns
        ]

        unmapped_columns = [
            ArtifactUnmappedColumn(
                header=column.header,
                source_column_index=column.source_column_index,
                output_header=column.output_header,
            )
            for column in table.mapped.column_map.unmapped_columns
        ]

        validation_issues = [
            ArtifactValidationIssue(
                row_index=issue.row_index,
                field=issue.field,
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                details=issue.details,
            )
            for issue in table.validation_issues
        ]

        table_entry = TableArtifact(
            source_file=str(extracted.source_file),
            source_sheet=extracted.source_sheet,
            table_index=extracted.table_index,
            header=TableHeader(row_index=extracted.header_row_index, cells=extracted.header_row),
            mapped_columns=mapped_columns,
            unmapped_columns=unmapped_columns,
            validation_issues=validation_issues,
        )
        self._artifact.tables.append(table_entry)

    def note(self, message: str, *, level: str = "info", details: dict | None = None) -> None:
        if not self._artifact:
            msg = "ArtifactSink.start must be called before recording notes."
            raise RuntimeError(msg)

        self._artifact.notes.append(
            ArtifactNote(
                timestamp=_format_timestamp(datetime.utcnow()) or "",
                level=level,
                message=message,
                details=details,
            )
        )

    def mark_success(self, outputs: Iterable[Path]) -> None:
        if not self._artifact:
            msg = "ArtifactSink.start must be called before marking success."
            raise RuntimeError(msg)

        self._artifact.run.status = RunStatus.SUCCEEDED
        if self._paths:
            self._artifact.run.outputs = _relative_paths(outputs, self._paths.output_dir)
        else:
            self._artifact.run.outputs = [str(path) for path in outputs]
        completed_at = self._run.completed_at if self._run else None
        completed_at = completed_at or datetime.utcnow()
        if self._run:
            self._run.completed_at = completed_at
        self._artifact.run.completed_at = _format_timestamp(completed_at)

    def mark_failure(self, error: RunError, *, details: dict | None = None) -> None:
        if not self._artifact:
            msg = "ArtifactSink.start must be called before marking failure."
            raise RuntimeError(msg)

        self._artifact.run.status = RunStatus.FAILED
        self._artifact.run.error = ArtifactError(
            code=error.code,
            stage=error.stage,
            message=error.message,
            details=details,
        )
        completed_at = self._run.completed_at if self._run else None
        completed_at = completed_at or datetime.utcnow()
        if self._run:
            self._run.completed_at = completed_at
        self._artifact.run.completed_at = _format_timestamp(completed_at)

    def flush(self) -> None:
        if not self._artifact:
            msg = "ArtifactSink.start must be called before flushing."
            raise RuntimeError(msg)

        artifact_dir = self.artifact_path.parent
        artifact_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.artifact_path.with_suffix(self.artifact_path.suffix + ".tmp")
        payload = json.dumps(self._artifact.model_dump(mode="json"), ensure_ascii=False)
        temp_path.write_text(payload)
        temp_path.replace(self.artifact_path)
