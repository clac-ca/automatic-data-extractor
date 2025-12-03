"""Pipeline orchestration utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from ade_engine.config.hook_registry import HookStage
from ade_engine.config.loader import ConfigRuntime
from ade_engine.core.hooks import run_hooks
from ade_engine.core.pipeline.extract import extract_raw_tables
from ade_engine.core.pipeline.mapping import map_extracted_tables
from ade_engine.core.pipeline.normalize import normalize_table
from ade_engine.core.pipeline.write import write_workbook
from ade_engine.core.types import NormalizedTable, RunContext, RunRequest
from ade_engine.infra.telemetry import EventEmitter


def _collect_processed_files(tables: Iterable[NormalizedTable]) -> tuple[str, ...]:
    names = {table.mapped.extracted.source_file.name for table in tables}
    return tuple(sorted(names))


def execute_pipeline(
    *,
    request: RunRequest,
    run: RunContext,
    runtime: ConfigRuntime,
    logger: logging.Logger,
    event_emitter: EventEmitter,
) -> tuple[list[NormalizedTable], tuple[Path, ...], tuple[str, ...]]:
    """Run all pipeline stages and return normalized tables and outputs."""

    event_emitter.phase_started("extracting")
    raw_tables = extract_raw_tables(
        request=request, run=run, runtime=runtime, logger=logger, event_emitter=event_emitter
    )
    extract_context = run_hooks(
        HookStage.ON_AFTER_EXTRACT,
        runtime.hooks,
        run=run,
        manifest=runtime.manifest,
        tables=raw_tables,
        workbook=None,
        result=None,
        logger=logger,
        event_emitter=event_emitter,
    )
    raw_tables = extract_context.tables or []

    event_emitter.phase_started("mapping")
    mapped_tables = map_extracted_tables(
        tables=raw_tables, runtime=runtime, run=run, logger=logger, event_emitter=event_emitter
    )
    mapping_context = run_hooks(
        HookStage.ON_AFTER_MAPPING,
        runtime.hooks,
        run=run,
        manifest=runtime.manifest,
        tables=mapped_tables,
        workbook=None,
        result=None,
        logger=logger,
        event_emitter=event_emitter,
    )
    mapped_tables = mapping_context.tables or []

    event_emitter.phase_started("normalizing")
    normalized_tables = [
        normalize_table(ctx=run, cfg=runtime, mapped=mapped, logger=logger, event_emitter=event_emitter)
        for mapped in mapped_tables
    ]
    for table in normalized_tables:
        event_emitter.table_summary(table)

    # Run-level validation summary (useful for validation-only mode and analytics).
    all_issues = [issue for table in normalized_tables for issue in table.validation_issues]
    event_emitter.validation_summary(all_issues)

    event_emitter.phase_started("writing_output")
    output_path = write_workbook(
        ctx=run,
        cfg=runtime,
        tables=normalized_tables,
        logger=logger,
        event_emitter=event_emitter,
    )

    processed_files = _collect_processed_files(normalized_tables)
    return normalized_tables, (output_path,), processed_files


__all__ = ["execute_pipeline"]
