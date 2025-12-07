from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.config.loader import ConfigRuntime
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.config.hook_registry import HookStage
from ade_engine.core.hooks import run_hooks
from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.infra.event_emitter import ConfigEventEmitter


def _build_header(table: NormalizedTable, *, append_unmapped: bool, manifest: ManifestContext) -> list:
    headers = []
    for mapped in table.mapped.column_map.mapped_columns:
        headers.append(mapped.field)
    if append_unmapped:
        headers.extend(unmapped.output_header for unmapped in table.mapped.column_map.unmapped_columns)
    return headers


def write_workbook(
    *,
    ctx: RunContext,
    cfg: ConfigRuntime,
    tables: list[NormalizedTable],
    input_file_name: str | None,
    event_emitter: ConfigEventEmitter,
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
            t.mapped.extracted.source_file.name,
            t.mapped.extracted.source_sheet or "",
            t.mapped.extracted.table_index,
        ),
    )

    output_dir = ctx.paths.output_dir
    output_file = ctx.paths.output_file
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()

    groups: dict[tuple[str, str | None], list[NormalizedTable]] = {}
    for table in sorted_tables:
        key = (str(table.mapped.extracted.source_file), table.mapped.extracted.source_sheet)
        groups.setdefault(key, []).append(table)

    used_names: set[str] = set()
    first_sheet = True

    for key in groups:
        tables_for_sheet = groups[key]
        exemplar = tables_for_sheet[0]
        base_name = exemplar.mapped.extracted.source_sheet or exemplar.mapped.extracted.source_file.stem or "Sheet"
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}-{suffix}"
            suffix += 1
        used_names.add(name)

        sheet = workbook.active if first_sheet else workbook.create_sheet(title=name)
        if first_sheet:
            sheet.title = name
            first_sheet = False

        header = _build_header(exemplar, append_unmapped=append_unmapped, manifest=cfg.manifest)
        sheet.append(header)

        for table in tables_for_sheet:
            table.output_sheet_name = name
            for row in table.rows:
                row_values = row if append_unmapped else row[: len(header)]
                sheet.append(row_values)

    before_save_context = run_hooks(
        HookStage.ON_BEFORE_SAVE,
        cfg.hooks,
        run=ctx,
        input_file_name=input_file_name,
        manifest=cfg.manifest,
        tables=sorted_tables,
        workbook=workbook,
        result=None,
        logger=logger,
        event_emitter=event_emitter,
    )
    workbook = before_save_context.workbook or workbook

    workbook.save(output_file)
    logger.info("Wrote normalized workbook", extra={"output": str(output_file)})
    return output_file


__all__ = ["write_workbook"]
