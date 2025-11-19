"""Extract and normalize inputs into structured tables."""

from __future__ import annotations

from typing import Any, Mapping

from ..logging import StructuredLogger
from ..model import JobContext
from ..schemas.models import ManifestContext
from .io import iter_tables, list_input_files, sheet_name
from .models import ColumnModule, FileExtraction
from .processing import process_table


def extract_inputs(
    job: JobContext,
    manifest: ManifestContext,
    modules: Mapping[str, ColumnModule],
    logger: StructuredLogger,
    *,
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    unmapped_prefix: str,
    state: dict[str, Any],
) -> list[FileExtraction]:
    """Process job input files and return normalized table extractions."""

    input_files = list_input_files(job.paths.input_dir)
    if not input_files:
        raise RuntimeError("No input files found for job")

    order = manifest.column_order
    meta = manifest.column_meta
    definitions = manifest.column_models

    runtime_logger = logger.runtime_logger
    results: list[FileExtraction] = []
    raw_sheet_names = job.metadata.get("input_sheet_names") if job.metadata else None
    sheet_list: list[str] | None = None
    if isinstance(raw_sheet_names, list):
        cleaned = [str(value).strip() for value in raw_sheet_names if str(value).strip()]
        sheet_list = cleaned or None
    elif raw_sheet_names:
        sheet_list = [str(raw_sheet_names).strip()]
    elif job.metadata and job.metadata.get("input_sheet_name"):
        sheet_list = [str(job.metadata["input_sheet_name"]).strip()]

    for file_path in input_files:
        targets = sheet_list if file_path.suffix.lower() == ".xlsx" else None
        for source_sheet, header_row, data_rows in iter_tables(
            file_path, sheet_names=targets
        ):
            table_info = {
                "headers": header_row,
                "rows": data_rows,
                "row_count": len(data_rows),
                "column_count": len(header_row),
                "source_name": file_path.name,
            }
            state.setdefault("tables", []).append(table_info)

            table_result = process_table(
                job=job,
                header_row=header_row,
                data_rows=data_rows,
                order=order,
                meta=meta,
                definitions=definitions,
                modules=modules,
                threshold=threshold,
                sample_size=sample_size,
                append_unmapped=append_unmapped,
                unmapped_prefix=unmapped_prefix,
                table_info=table_info,
                state=state,
                logger=runtime_logger,
            )

            normalized_sheet = (
                sheet_name(f"{file_path.stem}-{source_sheet}")
                if source_sheet
                else sheet_name(file_path.stem)
            )
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


__all__ = ["extract_inputs"]
