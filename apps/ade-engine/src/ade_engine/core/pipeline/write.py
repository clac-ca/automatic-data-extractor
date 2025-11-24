from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import Workbook

from ade_engine.config.loader import ConfigRuntime
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.config.hook_registry import HookStage
from ade_engine.core.hooks import run_hooks
from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.infra.telemetry import PipelineLogger


def _generate_sheet_name(table: NormalizedTable) -> str:
    raw = table.mapped.raw
    base = raw.source_file.stem
    if raw.source_sheet:
        base = f"{base}-{raw.source_sheet}"
    if raw.table_index > 0:
        base = f"{base}-{raw.table_index + 1}"

    # Excel limits sheet titles to 31 characters.
    base = base[:31] if len(base) > 31 else base
    return base or "Sheet"


def _unique_sheet_name(base: str, existing: set[str]) -> str:
    name = base
    counter = 2
    while name in existing:
        suffix = f"-{counter}"
        trimmed = base[: 31 - len(suffix)]
        name = f"{trimmed}{suffix}"
        counter += 1
    existing.add(name)
    return name


def _build_header(table: NormalizedTable, *, append_unmapped: bool, manifest: ManifestContext) -> list:
    headers = []
    for mapped in table.mapped.column_map.mapped_columns:
        meta = manifest.columns.fields.get(mapped.field)
        headers.append(meta.label if meta else mapped.field)
    if append_unmapped:
        headers.extend(unmapped.output_header for unmapped in table.mapped.column_map.unmapped_columns)
    return headers


def write_workbook(
    *,
    ctx: RunContext,
    cfg: ConfigRuntime,
    tables: list[NormalizedTable],
    pipeline_logger: PipelineLogger,
    logger: logging.Logger | None = None,
) -> Path:
    """Write normalized tables to an Excel workbook.

    Behavior follows ``05-normalization-and-validation.md`` and integrates hooks
    documented in ``08-hooks-and-extensibility.md``.
    """

    logger = logger or logging.getLogger(__name__)
    writer_cfg = cfg.manifest.writer
    append_unmapped = writer_cfg.append_unmapped_columns

    sorted_tables = sorted(
        tables,
        key=lambda t: (
            t.mapped.raw.source_file.name,
            t.mapped.raw.source_sheet or "",
            t.mapped.raw.table_index,
        ),
    )

    output_dir = ctx.paths.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()

    sheet_override = writer_cfg.output_sheet
    used_names: set[str] = set()

    def assign_sheet(table: NormalizedTable) -> tuple[Workbook, str]:
        nonlocal workbook
        if sheet_override:
            sheet = workbook.active
            sheet.title = sheet_override
            return sheet, sheet_override

        base = _generate_sheet_name(table)
        name = _unique_sheet_name(base, used_names)
        if not used_names:
            sheet = workbook.active
            sheet.title = name
        else:
            sheet = workbook.create_sheet(title=name)
        return sheet, name

    header_written = False
    for table in sorted_tables:
        sheet, title = assign_sheet(table)
        table.output_sheet_name = title

        header = _build_header(table, append_unmapped=append_unmapped, manifest=cfg.manifest)
        if sheet_override:
            if not header_written:
                sheet.append(header)
                header_written = True
        else:
            sheet.append(header)

        for row in table.rows:
            sheet.append(row)

    run_hooks(
        HookStage.ON_BEFORE_SAVE,
        cfg.hooks,
        run=ctx,
        manifest=cfg.manifest,
        artifact=pipeline_logger.artifact_sink,
        events=pipeline_logger.event_sink,
        tables=sorted_tables,
        workbook=workbook,
        result=None,
        logger=pipeline_logger,
    )

    output_path = output_dir / "normalized.xlsx"
    workbook.save(output_path)
    logger.info("Wrote normalized workbook", extra={"output": str(output_path)})
    return output_path


__all__ = ["write_workbook"]
