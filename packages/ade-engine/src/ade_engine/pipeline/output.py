"""Output composition helpers."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ..model import JobContext
from ..schemas.models import ManifestContext
from .models import FileExtraction


def write_outputs(
    job: JobContext,
    manifest: ManifestContext,
    extractions: list[FileExtraction],
) -> Path:
    """Persist normalized rows into an Excel workbook."""

    workbook = Workbook(write_only=True)

    try:
        for extraction in extractions:
            sheet = workbook.create_sheet(title=extraction.sheet_name)
            header_cells = output_headers(manifest, extraction)
            sheet.append(header_cells)
            for row in extraction.rows:
                sheet.append(row)

        output_path = job.paths.output_dir / "normalized.xlsx"
        tmp_path = output_path.with_suffix(".xlsx.tmp")
        workbook.save(tmp_path)
        tmp_path.replace(output_path)
        return output_path
    finally:
        workbook.close()


def output_headers(manifest: ManifestContext, extraction: FileExtraction) -> list[str]:
    """Build output headers combining manifest labels and unmapped columns."""

    order = manifest.column_order
    meta = manifest.column_meta
    headers = [meta.get(field, {}).get("label", field) for field in order]
    headers.extend(extra.output_header for extra in extraction.extra_columns)
    return headers


__all__ = ["output_headers", "write_outputs"]
