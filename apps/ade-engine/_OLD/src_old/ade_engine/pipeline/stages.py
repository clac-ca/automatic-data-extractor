"""Extract and write pipeline stages used by :class:`PipelineRunner`."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ade_engine.core.manifest import ManifestContext
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import ColumnModule, FileExtraction
from ade_engine.telemetry.logging import PipelineLogger

from .io import iter_tables, list_input_files, sheet_name
from .processing import process_table
from .util import unique_sheet_name
from . import output as writer


class ExtractStage:
    """Extract inputs into normalized tables."""

    def __init__(
        self,
        *,
        manifest: ManifestContext,
        modules: Mapping[str, ColumnModule],
        threshold: float,
        sample_size: int,
        append_unmapped: bool,
        unmapped_prefix: str,
    ) -> None:
        self._manifest = manifest
        self._modules = modules
        self._threshold = threshold
        self._sample_size = sample_size
        self._append_unmapped = append_unmapped
        self._unmapped_prefix = unmapped_prefix

    def run(
        self, job: JobContext, data: None, logger: PipelineLogger
    ) -> list[FileExtraction]:
        input_files = list_input_files(job.paths.input_dir)
        if not input_files:
            raise RuntimeError("No input files found for job")

        order = self._manifest.column_order
        meta = self._manifest.column_meta
        definitions = self._manifest.column_meta_models

        runtime_logger = logger.runtime_logger
        results: list[FileExtraction] = []
        used_sheet_names: set[str] = set()
        raw_sheet_names = job.metadata.get("input_sheet_names") if job.metadata else None
        sheet_list: list[str] | None = None
        if isinstance(raw_sheet_names, list):
            cleaned = [str(value).strip() for value in raw_sheet_names if str(value).strip()]
            sheet_list = cleaned or None

        for file_path in input_files:
            targets = sheet_list if file_path.suffix.lower() == ".xlsx" else None
            for source_sheet, header_row, data_rows in iter_tables(
                file_path, sheet_names=targets
            ):
                table_info = {
                    "headers": header_row,
                    "row_count": len(data_rows),
                    "column_count": len(header_row),
                    "source_name": file_path.name,
                    "sheet_name": source_sheet,
                }

                table_result = process_table(
                    job=job,
                    header_row=header_row,
                    data_rows=data_rows,
                    order=order,
                    meta=meta,
                    definitions=definitions,
                    modules=self._modules,
                    threshold=self._threshold,
                    sample_size=self._sample_size,
                    append_unmapped=self._append_unmapped,
                    unmapped_prefix=self._unmapped_prefix,
                    table_info=table_info,
                    state={},
                    logger=runtime_logger,
                )

                normalized_sheet = (
                    sheet_name(f"{file_path.stem}-{source_sheet}")
                    if source_sheet
                    else sheet_name(file_path.stem)
                )
                normalized_sheet = unique_sheet_name(normalized_sheet, used_sheet_names)
                extraction = FileExtraction(
                    source_name=file_path.name,
                    sheet_name=normalized_sheet,
                    mapped_columns=list(table_result.mapping),
                    extra_columns=list(table_result.extras),
                    rows=table_result.rows,
                    header_row=header_row,
                    validation_issues=table_result.issues,
                )

                logger.record_table(
                    {
                        "input_file": file_path.name,
                        "sheet": normalized_sheet,
                        "header": {"row_index": 1, "source": header_row},
                        "mapping": [
                            {
                                "field": entry.field,
                                "header": entry.header,
                                "source_column_index": entry.index,
                                "score": entry.score,
                                "contributions": [
                                    {
                                        "field": contrib.field,
                                        "detector": contrib.detector,
                                        "delta": contrib.delta,
                                    }
                                    for contrib in entry.contributions
                                ],
                            }
                            for entry in table_result.mapping
                        ],
                        "unmapped": [
                            {
                                "header": extra.header,
                                "source_column_index": extra.index,
                                "output_header": extra.output_header,
                            }
                            for extra in table_result.extras
                        ],
                        "validation": table_result.issues,
                    }
                )
                logger.note(
                    f"Processed input file {file_path.name}",
                    mapped_fields=[entry.field for entry in table_result.mapping],
                )
                logger.flush()
                logger.event(
                    "file_processed",
                    file=file_path.name,
                    mapped_fields=[entry.field for entry in table_result.mapping],
                    validation_issue_count=len(table_result.issues),
                )
                for issue in table_result.issues:
                    logger.event(
                        "validation_issue",
                        level="warning",
                        file=file_path.name,
                        row_index=issue.get("row_index"),
                        field=issue.get("field"),
                        code=issue.get("code"),
                    )

                results.append(extraction)

        return results


class WriteStage:
    """Write normalized outputs."""

    def __init__(self, *, manifest: ManifestContext) -> None:
        self._manifest = manifest

    def run(
        self, job: JobContext, tables: list[FileExtraction], logger: PipelineLogger
    ) -> Path | Sequence[Path]:
        return writer.write_outputs(job, self._manifest, tables)


__all__ = ["ExtractStage", "WriteStage"]
