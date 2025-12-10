from __future__ import annotations

import logging
from typing import Any, Dict, List

from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.pipeline.detect_rows import detect_table_bounds
from ade_engine.pipeline.detect_columns import detect_and_map_columns, build_source_columns
from ade_engine.pipeline.transform import apply_transforms
from ade_engine.pipeline.validate import apply_validators
from ade_engine.pipeline.render import render_table
from ade_engine.pipeline.models import TableData
from ade_engine.registry.models import HookContext, HookName
from ade_engine.registry.registry import Registry
from ade_engine.settings import Settings
from ade_engine.logging import RunLogger


class Pipeline:
    """Orchestrates sheet-level processing using the registry."""

    def __init__(self, *, registry: Registry, settings: Settings, logger: RunLogger) -> None:
        self.registry = registry
        self.settings = settings
        self.logger = logger

    def _run_hooks(self, hook_name: HookName, *, state: dict, run_metadata: dict, workbook=None, sheet=None, table=None):
        hooks = self.registry.hooks.get(hook_name, [])
        if not hooks:
            return
        ctx = HookContext(
            hook_name=hook_name,
            run_metadata=run_metadata,
            state=state,
            workbook=workbook,
            sheet=sheet,
            table=table,
            logger=self.logger,
        )
        for hook_def in hooks:
            self.logger.event(
                "hook.start",
                level=logging.DEBUG,
                data={
                    "hook_name": hook_name.value if hasattr(hook_name, "value") else str(hook_name),
                    "hook": hook_def.qualname,
                },
            )
            hook_def.fn(ctx)
            self.logger.event(
                "hook.end",
                level=logging.DEBUG,
                data={
                    "hook_name": hook_name.value if hasattr(hook_name, "value") else str(hook_name),
                    "hook": hook_def.qualname,
                },
            )

    def process_sheet(
        self,
        *,
        sheet: Worksheet,
        output_sheet: Worksheet,
        state: dict,
        run_metadata: dict,
        table_index: int = 0,
    ) -> TableData:
        rows: List[List[Any]] = [list(row) for row in sheet.iter_rows(values_only=True)]
        header_idx, data_start_idx, data_end_idx = detect_table_bounds(
            sheet_name=sheet.title,
            rows=rows,
            registry=self.registry,
            state=state,
            run_metadata=run_metadata,
            logger=self.logger,
        )
        header_row = rows[header_idx] if header_idx < len(rows) else []
        data_rows = rows[data_start_idx:data_end_idx]

        mapped_cols, unmapped_cols = detect_and_map_columns(
            sheet_name=sheet.title,
            header_row=header_row,
            data_rows=data_rows,
            registry=self.registry,
            settings=self.settings,
            state=state,
            run_metadata=run_metadata,
            logger=self.logger,
        )
        source_cols = build_source_columns(header_row, data_rows)

        table = TableData(
            sheet_name=sheet.title,
            header_row_index=header_idx,
            source_columns=source_cols,
            mapped_columns=mapped_cols,
            unmapped_columns=unmapped_cols,
        )

        # Hook: table detected
        self._run_hooks(
            HookName.ON_TABLE_DETECTED,
            state=state,
            run_metadata=run_metadata,
            workbook=None,
            sheet=sheet,
            table=table,
        )

        # Hook: allow mapping reorder/patch
        self._run_hooks(
            HookName.ON_TABLE_MAPPED,
            state=state,
            run_metadata=run_metadata,
            workbook=None,
            sheet=sheet,
            table=table,
        )

        transformed_rows = apply_transforms(
            mapped_columns=table.mapped_columns,
            registry=self.registry,
            state=state,
            run_metadata=run_metadata,
            logger=self.logger,
        )
        table.rows = transformed_rows

        issues = apply_validators(
            mapped_columns=table.mapped_columns,
            transformed_rows=transformed_rows,
            registry=self.registry,
            state=state,
            run_metadata=run_metadata,
            logger=self.logger,
        )
        table.issues = issues

        render_table(
            table=table,
            worksheet=output_sheet,
            settings=self.settings,
            table_index=table_index,
            logger=self.logger,
        )

        # Hook after write
        self._run_hooks(
            HookName.ON_TABLE_WRITTEN,
            state=state,
            run_metadata=run_metadata,
            workbook=output_sheet.parent,
            sheet=output_sheet,
            table=table,
        )
        return table


__all__ = ["Pipeline"]
